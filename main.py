"""
Agent Twitter — Veille IA & Tech
================================

Orchestrateur principal :
  - Scan des flux RSS IA & Tech
  - Sélection du meilleur article non encore publié (anti-doublons SQLite)
  - Génération d'un tweet en français par l'IA (DeepSeek / OpenAI)
  - Publication sur Twitter/X (API V2)
  - Planification : 2 exécutions par jour (défaut 08:30 et 17:30 UTC)

Déploiement continu : Render / Railway Worker (`worker: python main.py`)
"""

import logging
import sys
import time
from datetime import datetime, timezone

import schedule

import config
import database
import rss_parser
import ai_generator
import twitter_client

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
# Conversion des heures UTC → heure locale du serveur
# ─────────────────────────────────────────────────────────────
def _utc_to_local(hh_mm: str) -> str:
    """
    Convertit une heure au format 'HH:MM' UTC en heure locale du serveur.

    Exemple : si le serveur est à UTC+2, "08:30" UTC → "10:30" local.
    """
    try:
        hours, minutes = hh_mm.split(":")
        utc_dt = datetime.now(timezone.utc).replace(
            hour=int(hours), minute=int(minutes), second=0, microsecond=0
        )
        local_dt = utc_dt.astimezone()
        return local_dt.strftime("%H:%M")
    except (ValueError, TypeError) as exc:
        logger.warning("Heure de planification invalide '%s' — ignorée. Erreur : %s", hh_mm, exc)
        return None


# ─────────────────────────────────────────────────────────────
# Exécution d'un cycle complet (1 tweet maximum)
# ─────────────────────────────────────────────────────────────
def run_once() -> bool:
    """
    Exécute un cycle complet :
      1. Récupère les nouveaux articles des flux RSS
      2. Sélectionne le meilleur article (le plus récent non publié)
      3. Génère un tweet en français via l'IA
      4. Publie le tweet sur Twitter/X

    :return: True si un tweet a été publié, False sinon
    """
    logger.info("=== Début du cycle de veille ===")

    # 1. Récupération des nouveaux articles (anti-doublons)
    new_articles = rss_parser.fetch_new_articles()

    if not new_articles:
        logger.info("Aucun nouvel article à publier — fin du cycle.")
        return False

    # 2. Sélection : l'article le plus récent (liste déjà triée récent → ancien)
    best_article = new_articles[0]
    logger.info(
        "Article sélectionné : « %s » (%s)",
        best_article.title,
        best_article.source,
    )

    # 3. Génération du tweet par l'IA
    tweet = ai_generator.generate_tweet(
        title=best_article.title,
        url=best_article.url,
        source=best_article.source,
        summary=best_article.summary,
    )

    if not tweet:
        logger.error("Génération IA échouée — article marqué comme traité pour éviter de rebloquer.")
        database.mark_article_processed(
            url=best_article.url,
            title=best_article.title,
            source=best_article.source,
        )
        return False

    logger.info("Tweet généré (%d caractères) : %s", len(tweet), tweet)

    # 4. Publication
    twitter = twitter_client.TwitterClient()
    if not twitter.configure():
        logger.error("Échec de configuration Twitter — impossible de publier.")
        return False

    published = twitter.post_tweet(tweet)

    # Enregistrement en base (publié ou non) pour éviter les re-tentatives sans fin
    database.mark_article_processed(
        url=best_article.url,
        title=best_article.title,
        source=best_article.source,
        tweet_text=tweet,
    )

    stats = database.get_statistics()
    logger.info(
        "Fin du cycle — publié=%s | article « %s » | total traité : %d",
        published,
        best_article.title[:40],
        stats.get("count", 0),
    )
    return published


# ─────────────────────────────────────────────────────────────
# Planification avec `schedule` (2 fois par jour, en UTC)
# ─────────────────────────────────────────────────────────────
def setup_schedule() -> None:
    """Planifie les exécutions selon config.SCHEDULE_TIMES (heures UTC)."""
    scheduled_count = 0

    for time_str in config.SCHEDULE_TIMES:
        local_time = _utc_to_local(time_str)
        if local_time is None:
            continue

        schedule.every().day.at(local_time).do(run_once)
        logger.info(
            "Exécution planifiée : %s UTC → %s heure locale du serveur",
            time_str,
            local_time,
        )
        scheduled_count += 1

    if scheduled_count == 0:
        logger.warning(
            "Aucune heure de planification valide — le mode TEST_ON_STARTUP reste disponible."
        )


# ─────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────
def main() -> None:
    """Boucle principale : planification 2x/jour + exécution test optionnelle."""
    logger.info("🚀 Démarrage de l'agent Twitter — Veille IA & Tech")
    logger.info("Heure serveur (UTC) : %s", datetime.now(timezone.utc).strftime("%H:%M:%S"))

    # Mode simulation (Dry-Run) — alerte claire au démarrage
    if config.DRY_RUN:
        logger.warning(
            "🧪 MODE DRY-RUN ACTIVÉ — les tweets seront affichés dans la console "
            "et NE SERONT PAS publiés sur Twitter. Mettez DRY_RUN=false dans .env "
            "pour activer la publication réelle."
        )
    else:
        logger.info("Mode publication réel ACTIVÉ — les tweets seront envoyés sur Twitter/X.")

    # 1. Initialisation de la base de données
    database.init_db()
    stats = database.get_statistics()
    logger.info("Base de données : %s (articles traités : %d)", config.DB_PATH, stats.get("count", 0))

    # 2. Vérification de la configuration Twitter
    console_twitter = twitter_client.TwitterClient()
    if not console_twitter.configure():
        logger.warning("Twitter non configuré — les publications échoueront. Vérifiez .env")

    # 3. Planification
    setup_schedule()

    # 4. Exécution de test immédiate (optionnelle)
    if config.TEST_ON_STARTUP:
        logger.info("⚠️  Mode TEST_ON_STARTUP activé — exécution immédiate du cycle")
        run_once()
    else:
        logger.info("TEST_ON_STARTUP=false — le premier tweet sera publié à l'heure planifiée.")

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