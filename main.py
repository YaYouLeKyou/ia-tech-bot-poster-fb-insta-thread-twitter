"""
Agent Twitter — Veille IA & Tech + Breaking News Web
====================================================

Orchestrateur principal :
  - Scan des flux RSS IA & Tech
  - Génération d'une breaking news AI
  - Publication automatique sur Twitter/X (API V2)
  - Affichage sur une page web (Flask)

Planification : 2 tweets/jour (défaut 08:30 & 17:30 UTC)
Déploiement : Render / Railway Worker (`worker: python main.py`)
"""

import logging
import sys
import threading
import time
from datetime import datetime, timezone

import schedule

import config
import database
import facebook_client
import news_service
import twitter_client
import web_app

# ─────────────────────────────────────────────────────────────
# Journalisation (logs clairs formatés pour dashboard serveur)
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("agent-twitter")


# ─────────────────────────────────────────────────────────────
# Publication d'un tweet sur Twitter
# ─────────────────────────────────────────────────────────────
def publish_news_tweet(news: dict) -> bool:
    """
    Publie la breaking news générée sur Twitter (ou simule en dry-run).

    :param news: dict avec breaking_text, title, url
    :return: True si publié (ou simulé), False sinon
    """
    if not news or not news.get("breaking_text"):
        logger.warning("Aucun texte de tweet à publier")
        return False

    # Si Twitter n'est pas configuré, on log simplement
    if not config.TWITTER_API_KEY or not config.TWITTER_API_SECRET:
        logger.warning(
            "Twitter non configuré — tweet non publié. "
            "Renseignez TWITTER_API_KEY et TWITTER_API_SECRET dans .env"
        )
        return False

    try:
        twitter = twitter_client.TwitterClient()
        if not twitter.configure():
            logger.error("Échec de la configuration Twitter")
            return False

        published = twitter.post_tweet(news["breaking_text"])
        if published:
            logger.info("✅ Tweet publié : %s", news["title"][:60])
        else:
            logger.error("❌ Échec de la publication du tweet")
        return published

    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la publication Twitter : %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# Publication d'un post sur Facebook
# ─────────────────────────────────────────────────────────────
def publish_news_facebook(news: dict) -> bool:
    """
    Publie la breaking news générée sur la page Facebook (ou simule en dry-run).

    :param news: dict avec breaking_text, title, url
    :return: True si publié (ou simulé), False sinon
    """
    if not news or not news.get("breaking_text"):
        logger.warning("Aucun texte de post à publier sur Facebook")
        return False

    # Si Facebook n'est pas configuré, on log simplement
    if not config.META_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        logger.warning(
            "Facebook non configuré — post non publié. "
            "Renseignez META_ACCESS_TOKEN et FACEBOOK_PAGE_ID dans .env"
        )
        return False

    try:
        facebook = facebook_client.FacebookClient()
        if not facebook.configure():
            logger.error("Échec de la configuration Facebook")
            return False

        message = news["breaking_text"]
        link = news.get("url", "")
        published = facebook.post_to_page(message=message, link=link)
        if published:
            logger.info("✅ Post Facebook publié : %s", news["title"][:60])
        else:
            logger.error("❌ Échec de la publication du post Facebook")
        return published

    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la publication Facebook : %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# Génération + publication d'une breaking news
# ─────────────────────────────────────────────────────────────
def generate_news_job() -> None:
    """Génère une nouvelle breaking news et la publie sur Twitter + Facebook."""
    logger.info("=== Génération planifiée d'une breaking news ===")
    news = news_service.generate_breaking_news()
    if news:
        logger.info("✅ Breaking news générée : %s", news["title"][:60])
        # Publication sur Twitter (respecte DRY_RUN via twitter_client)
        publish_news_tweet(news)
        # Publication sur Facebook (respecte DRY_RUN via facebook_client)
        publish_news_facebook(news)
    else:
        logger.warning("⚠️  Échec de la génération de la breaking news")


# ─────────────────────────────────────────────────────────────
# Planification avec `schedule` (2 fois par jour)
# ─────────────────────────────────────────────────────────────
def setup_schedule() -> None:
    """Planifie la génération des breaking news aux heures configurées."""
    schedule_times = config.SCHEDULE_TIMES
    for time_str in schedule_times:
        schedule.every().day.at(time_str).do(generate_news_job)
        logger.info("Breaking news planifiée : %s UTC", time_str)

    # Planification alternative : toutes les N heures si configuré
    # (utilisé si SCHEDULE_TIMES est vide)
    if not schedule_times:
        interval = config.NEWS_INTERVAL_HOURS
        schedule.every(interval).hours.do(generate_news_job)
        logger.info("Breaking news planifiée : toutes les %d heures", interval)


# ─────────────────────────────────────────────────────────────
# Lancement du serveur web en arrière-plan
# ─────────────────────────────────────────────────────────────
def start_web_server() -> None:
    """Démarre le serveur web Flask dans un thread séparé."""
    web_port = int(config.WEB_PORT)
    web_thread = threading.Thread(
        target=web_app.run_web_server,
        kwargs={"host": "0.0.0.0", "port": web_port},
        daemon=True,
    )
    web_thread.start()
    logger.info("🌐 Serveur web démarré sur le port %d", web_port)


# ─────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────
def main() -> None:
    """Boucle principale : planification + publication + serveur web."""
    logger.info("🚀 Démarrage de l'agent — Veille IA & Tech + Breaking News")
    logger.info("Heure serveur (UTC) : %s", datetime.now(timezone.utc).strftime("%H:%M:%S"))
    logger.info("Mode dry-run : %s", config.DRY_RUN)

    # 1. Initialisation de la base de données
    database.init_db()
    stats = database.get_statistics()
    logger.info("Base de données : %s (articles traités : %d)", config.DB_PATH, stats.get("count", 0))

    # 2. Planification des breaking news
    setup_schedule()

    # 3. Test au démarrage si activé
    if config.TEST_ON_STARTUP:
        logger.info("TEST_ON_STARTUP=true — exécution immédiate d'un cycle complet")
        generate_news_job()
    else:
        # Génération immédiate d'une première breaking news (sans publication)
        logger.info("Génération de la première breaking news…")
        news = news_service.generate_breaking_news()
        if news:
            logger.info("✅ Breaking news initiale générée : %s", news["title"][:60])
        else:
            logger.warning("⚠️  Échec de la génération initiale")

    # 4. Lancement du serveur web
    start_web_server()

    # 5. Boucle infinie du worker
    logger.info("Boucle de planification active (Ctrl+C pour arrêter)…")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur — bye!")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        logger.critical("Erreur fatale dans la boucle principale : %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()