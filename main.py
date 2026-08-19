"""
Agent Twitter — Veille IA & Tech + Breaking News Web
====================================================

Orchestrateur principal :
  - Scan des flux RSS IA & Tech
  - Génération d'une breaking news AI
  - Publication automatique sur Twitter/X (API V2)
  - Publication automatique sur Facebook + Instagram (Meta Graph API)
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
import email_notifier
import facebook_client
import news_service
import token_renewal
import twitter_client
import web_app
from web_app import _build_long_post_message

# Import de la fonction utilitaire pour le fallback d'image Instagram
from facebook_client import get_valid_instagram_image

# Conversion heure de Paris ↔ UTC
from config import paris_time_to_utc, utc_time_to_paris

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
    if not config.FB_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        logger.warning(
            "Facebook non configuré — post non publié. "
            "Renseignez FB_PAGE_ACCESS_TOKEN et FACEBOOK_PAGE_ID dans .env"
        )
        return False

    try:
        facebook = facebook_client.FacebookClient()
        if not facebook.configure():
            logger.error("Échec de la configuration Facebook")
            # Envoi d'une alerte email si le token est expiré/invalide
            email_notifier.send_token_expired_alert(
                platform="Facebook",
                token_name="FB_PAGE_ACCESS_TOKEN",
                error_detail="Token Facebook invalide ou expiré (échec de configuration)",
            )
            return False

        message = _build_long_post_message(news)
        link = news.get("url", "")
        published = facebook.post_to_page(message=message, link=link)
        if published:
            logger.info("✅ Post Facebook publié : %s", news["title"][:60])
        else:
            logger.error("❌ Échec de la publication du post Facebook")
            # Vérifie si l'échec est dû à un token expiré
            if facebook.is_token_expired_error():
                email_notifier.send_token_expired_alert(
                    platform="Facebook",
                    token_name="FB_PAGE_ACCESS_TOKEN",
                    error_detail=facebook.last_error_message,
                )
        return published

    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la publication Facebook : %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# Publication d'un post sur Instagram
# ─────────────────────────────────────────────────────────────
def publish_news_instagram(news: dict) -> bool:
    """
    Publie la breaking news générée sur Instagram (ou simule en dry-run).

    :param news: dict avec breaking_text, title, url, image
    :return: True si publié (ou simulé), False sinon
    """
    if not news or not news.get("breaking_text"):
        logger.warning("Aucun texte de post à publier sur Instagram")
        return False

    if not config.FB_PAGE_ACCESS_TOKEN or not config.INSTAGRAM_ACCOUNT_ID:
        logger.warning(
            "Instagram non configuré — post non publié. "
            "Renseignez FB_PAGE_ACCESS_TOKEN et INSTAGRAM_ACCOUNT_ID dans .env"
        )
        return False

    try:
        facebook = facebook_client.FacebookClient()
        if not facebook.configure():
            logger.error("Échec de la configuration Facebook/Instagram")
            # Envoi d'une alerte email si le token est expiré/invalide
            email_notifier.send_token_expired_alert(
                platform="Instagram",
                token_name="FB_PAGE_ACCESS_TOKEN",
                error_detail="Token Facebook/Instagram invalide ou expiré (échec de configuration)",
            )
            return False

        message = _build_long_post_message(news)
        image_url = get_valid_instagram_image(
            caption=message,
            user_image_url=news.get("image") or "",
            title=news.get("title", ""),
        )
        published = facebook.post_to_instagram(message=message, image_url=image_url)
        if published:
            logger.info("✅ Post Instagram publié : %s", news["title"][:60])
        else:
            logger.error("❌ Échec de la publication du post Instagram")
            # Vérifie si l'échec est dû à un token expiré
            if facebook.is_token_expired_error():
                email_notifier.send_token_expired_alert(
                    platform="Instagram",
                    token_name="FB_PAGE_ACCESS_TOKEN",
                    error_detail=facebook.last_error_message,
                )
        return published

    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la publication Instagram : %s", exc)
        return False


def publish_news_threads(news: dict) -> bool:
    """
    Publie la breaking news générée sur Threads (ou simule en dry-run).

    :param news: dict avec breaking_text, title, url, image
    :return: True si publié (ou simulé), False sinon
    """
    if not news or not news.get("breaking_text"):
        logger.warning("Aucun texte de post à publier sur Threads")
        return False

    if not config.THREADS_ACCESS_TOKEN or not config.THREADS_USER_ID:
        logger.warning(
            "Threads non configuré — post non publié. "
            "Renseignez THREADS_ACCESS_TOKEN et THREADS_USER_ID dans .env"
        )
        return False

    try:
        facebook = facebook_client.FacebookClient()
        # Threads utilise son propre token — pas besoin de vérifier le token Facebook
        facebook._is_configured = True

        image_url = news.get("image", "") or ""
        published = facebook.post_to_threads(message=news["breaking_text"], image_url=image_url)
        if published:
            logger.info("✅ Post Threads publié : %s", news["title"][:60])
        else:
            logger.error("❌ Échec de la publication du post Threads")
            # Vérifie si l'échec est dû à un token expiré
            if facebook.is_token_expired_error():
                email_notifier.send_token_expired_alert(
                    platform="Threads",
                    token_name="THREADS_ACCESS_TOKEN",
                    error_detail=facebook.last_error_message,
                )
        return published

    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la publication Threads : %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# Génération + publication d'une breaking news
# ─────────────────────────────────────────────────────────────
def generate_news_job() -> None:
    """Génère une nouvelle breaking news et la publie sur Twitter + Facebook + Instagram + Threads."""
    logger.info("=== Génération planifiée d'une breaking news ===")
    news = news_service.generate_breaking_news()
    if news:
        logger.info("✅ Breaking news générée : %s", news["title"][:60])
        publish_news_tweet(news)
        publish_news_facebook(news)
        publish_news_instagram(news)
        publish_news_threads(news)
    else:
        logger.warning("⚠️  Échec de la génération de la breaking news")


# ─────────────────────────────────────────────────────────────
# Renouvellement automatique des tokens API
# ─────────────────────────────────────────────────────────────
def renew_tokens_job() -> None:
    """
    Vérifie et renouvelle les tokens Facebook et Threads.
    Planifié tous les TOKEN_RENEWAL_DAYS jours (défaut : 30).
    Envoie une notification email si un token est expiré ou invalide.
    """
    logger.info("=== Renouvellement automatique des tokens API ===")
    try:
        results = token_renewal.renew_all_tokens(send_email=True)
        for platform, result in results.items():
            status = result.get("status", "inconnu")
            logger.info("  %-10s : %s", platform.upper(), status)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors du renouvellement des tokens : %s", exc)
        email_notifier.send_generic_alert(
            subject="⚠️ Erreur lors du renouvellement automatique des tokens",
            body=(
                "Une erreur est survenue lors du renouvellement automatique des tokens.\n"
                f"Erreur : {exc}\n"
                f"Date : {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}"
            ),
        )


# ─────────────────────────────────────────────────────────────
# Planification avec `schedule`
# ─────────────────────────────────────────────────────────────
_schedule_lock = threading.Lock()


def _clear_schedule() -> None:
    """Supprime tous les jobs planifiés (thread-safe)."""
    with _schedule_lock:
        schedule.clear()


def setup_schedule() -> None:
    """Planifie la génération des breaking news aux heures configurées."""
    with _schedule_lock:
        schedule_times = config.SCHEDULE_TIMES
        interval = config.NEWS_INTERVAL_HOURS

        if interval > 0 and interval is not None:
            schedule.every(interval).hours.do(generate_news_job)
            logger.info("Breaking news planifiée : toutes les %d heures", interval)
        else:
            for time_str in schedule_times:
                # Les heures de la config sont TOUJOURS en heure de Paris.
                # Le paramètre `tz` de schedule gère automatiquement l'heure
                # d'été (UTC+2) et l'heure d'hiver (UTC+1) — pas de conversion manuelle.
                schedule.every().day.at(time_str, tz=config.LOCAL_TIMEZONE).do(generate_news_job)
                logger.info("Breaking news planifiée : %s (heure Paris)", time_str)

            if not schedule_times:
                # Protection contre schedule.every(0).hours (heure locale invalide).
                # Si NEWS_INTERVAL_HOURS=0 et aucune heure fixe, on utilise 6h.
                default_interval = interval if interval > 0 else 6
                schedule.every(default_interval).hours.do(generate_news_job)
                logger.info("Breaking news planifiée : toutes les %d heures", default_interval)

        # Renouvellement automatique des tokens API
        # Tous les TOKEN_RENEWAL_DAYS jours (défaut : 30) — les tokens Meta
        # durent 60 jours, ce renouvellement garantit qu'ils ne expirent jamais.
        renewal_days = config.TOKEN_RENEWAL_DAYS
        if renewal_days > 0:
            schedule.every(renewal_days).days.do(renew_tokens_job)
            logger.info(
                "Renouvellement des tokens API planifié : tous les %d jours",
                renewal_days,
            )
        else:
            logger.warning(
                "Renouvellement automatique des tokens désactivé (TOKEN_RENEWAL_DAYS=%d)",
                renewal_days,
            )


def reschedule_global() -> None:
    """
    Re-planifie l'ensemble des publications à partir de la config courante.
    Utilisé par l'interface web quand l'utilisateur change les heures
    ou la fréquence depuis le dashboard.
    """
    _clear_schedule()
    setup_schedule()
    logger.info("Planification globale mise à jour")


def _catch_up_missed_posts(schedule_times: list) -> bool:
    """
    Vérifie si une publication planifiée a été manquée au démarrage
    ou lors d'un réveil du worker (ex: plan gratuit Render qui s'endort
    après 15 min d'inactivité).

    Limite le rattrapage à UN SEUL post par appel pour éviter un flood
    de publications lors du redémarrage du service.

    :return: True si un post de rattrapage a été exécuté, False sinon
    """
    if not schedule_times or config.NEWS_INTERVAL_HOURS > 0:
        return False

    # Les heures sont en heure de Paris — nous devons comparer en heure de Paris
    from zoneinfo import ZoneInfo
    paris_tz = ZoneInfo(config.LOCAL_TIMEZONE)
    now = datetime.now(paris_tz)  # heure de Paris
    current_time = now.strftime("%H:%M")

    # Récupère les posts publiés aujourd'hui (publiés en UTC, convertis en heure Paris)
    published_times_today = set()
    history = database.get_breaking_news_history(limit=50)
    for item in history:
        try:
            published_dt = datetime.fromisoformat(item.get("published_at", ""))
            # Le timestamp est stocké en UTC — on le convertit en heure de Paris
            paris_dt = published_dt.astimezone(paris_tz)
            if paris_dt.date() == now.date():
                published_times_today.add(paris_dt.strftime("%H:%M"))
        except (ValueError, TypeError):
            continue

    # Vérifie chaque heure planifiée (ordonnée pour un rattrapage logique)
    for scheduled_time in sorted(schedule_times):
        # Si l'heure planifiée (Paris) est passée et qu'aucun post n'a été fait à cette heure
        if current_time >= scheduled_time and scheduled_time not in published_times_today:
            logger.info(
                "Post planifié à %s (heure Paris) manqué (dernier post : %s) — rattrapage en cours",
                scheduled_time,
                sorted(published_times_today) if published_times_today else "aucun",
            )
            try:
                generate_news_job()
                reschedule_global()
                logger.info("Rattrapage terminé — un post manqué a été publié")
                return True
            except Exception as exc:  # noqa: BLE001
                logger.error("Erreur lors du post de rattrapage : %s", exc)
                return False

    logger.info("Aucun post manqué — tous les posts planifiés ont été publiés")
    return False


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
def _generate_initial_news() -> None:
    """Génère la première breaking news en arrière-plan (thread séparé)."""
    try:
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
    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la génération initiale : %s", exc)


def _check_tokens_on_startup() -> None:
    """
    Vérifie la validité des tokens API au démarrage (thread séparé).
    Envoie une notification email si un token est expiré ou invalide.
    """
    logger.info("Vérification des tokens API au démarrage…")
    try:
        results = token_renewal.renew_all_tokens(send_email=True)
        for platform, result in results.items():
            status = result.get("status", "inconnu")
            logger.info("  %-10s : %s", platform.upper(), status)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la vérification des tokens au démarrage : %s", exc)


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
    reschedule_global()

    # 2bis. Rattrapage des posts manqués au démarrage
    _catch_up_missed_posts(config.SCHEDULE_TIMES)

    # 3. Lancement du serveur web IMMÉDIATEMENT (avant la génération initiale)
    start_web_server()

    # 4. Génération initiale en arrière-plan (thread séparé)
    #    Le serveur web est déjà accessible pendant le scan des flux RSS
    initial_thread = threading.Thread(target=_generate_initial_news, daemon=True)
    initial_thread.start()

    # 4bis. Vérification des tokens API au démarrage (thread séparé)
    #    Envoie une notification email si un token est expiré ou invalide
    token_check_thread = threading.Thread(target=_check_tokens_on_startup, daemon=True)
    token_check_thread.start()

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
