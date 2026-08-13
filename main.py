"""
Agent Twitter — Veille IA & Tech + Breaking News Web
====================================================

Orchestrateur principal :
  - Scan des flux RSS IA & Tech
  - Génération d'une breaking news AI toutes les 2 heures
  - Affichage sur une page web (Flask)
  - Publication optionnelle sur Twitter/X (API V2)

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
import news_service
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
# Génération d'une breaking news (toutes les 2 heures)
# ─────────────────────────────────────────────────────────────
def generate_news_job() -> None:
    """Génère une nouvelle breaking news AI."""
    logger.info("=== Génération planifiée d'une breaking news ===")
    news = news_service.generate_breaking_news()
    if news:
        logger.info("✅ Breaking news générée : %s", news["title"][:60])
    else:
        logger.warning("⚠️  Échec de la génération de la breaking news")


# ─────────────────────────────────────────────────────────────
# Planification avec `schedule` (toutes les 2 heures)
# ─────────────────────────────────────────────────────────────
def setup_schedule() -> None:
    """Planifie la génération des breaking news toutes les 2 heures."""
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
    """Boucle principale : planification 2h + serveur web."""
    logger.info("🚀 Démarrage de l'agent — Veille IA & Tech + Breaking News")
    logger.info("Heure serveur (UTC) : %s", datetime.now(timezone.utc).strftime("%H:%M:%S"))

    # 1. Initialisation de la base de données
    database.init_db()
    stats = database.get_statistics()
    logger.info("Base de données : %s (articles traités : %d)", config.DB_PATH, stats.get("count", 0))

    # 2. Planification des breaking news (toutes les 2 heures)
    setup_schedule()

    # 3. Génération immédiate d'une première breaking news
    logger.info("Génération de la première breaking news…")
    generate_news_job()

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