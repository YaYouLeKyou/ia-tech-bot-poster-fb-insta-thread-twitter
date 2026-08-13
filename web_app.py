"""
Application Web — Affichage des Breaking News AI.

Sert une page web qui affiche la dernière breaking news générée
par le scraper, avec :
  - Choix de la fréquence de mise à jour (2h, 4h, 8h... 48h)
  - Bouton "Tweet Now" pour publier en direct
  - Simulation visuelle du tweet pour validation
"""

import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

import config
import database
import news_service
import twitter_client

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Fréquences disponibles (en heures)
AVAILABLE_INTERVALS = [2, 4, 8, 12, 24, 48]


def _format_date(iso_str: str) -> str:
    """Convertit une date ISO en format lisible."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except (ValueError, TypeError):
        return iso_str


@app.route("/")
def index():
    """Page principale : affiche la dernière breaking news + historique."""
    latest = news_service.get_latest_news()
    history = news_service.get_all_news(limit=20)

    # Formatage des dates pour l'affichage
    if latest:
        latest["published_at_display"] = _format_date(latest.get("published_at", ""))
    for item in history:
        item["published_at_display"] = _format_date(item.get("published_at", ""))

    stats = database.get_statistics()
    current_interval = config.NEWS_INTERVAL_HOURS

    # Vérifie si Twitter est configuré
    twitter_configured = bool(config.TWITTER_API_KEY and config.TWITTER_API_SECRET)

    return render_template(
        "index.html",
        latest=latest,
        history=history,
        stats=stats,
        now=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        available_intervals=AVAILABLE_INTERVALS,
        current_interval=current_interval,
        twitter_configured=twitter_configured,
        dry_run=config.DRY_RUN,
    )


@app.route("/api/latest")
def api_latest():
    """API JSON : dernière breaking news."""
    latest = news_service.get_latest_news()
    if not latest:
        return jsonify({"error": "Aucune breaking news disponible"}), 404
    return jsonify(latest)


@app.route("/api/history")
def api_history():
    """API JSON : historique des breaking news."""
    history = news_service.get_all_news(limit=50)
    return jsonify(history)


@app.route("/api/refresh")
def api_refresh():
    """API JSON : force la génération d'une nouvelle breaking news."""
    news = news_service.generate_breaking_news()
    if not news:
        return jsonify({"error": "Échec de la génération"}), 500
    return jsonify(news)


@app.route("/api/interval", methods=["POST"])
def api_set_interval():
    """API : change la fréquence de mise à jour (en heures)."""
    data = request.get_json(silent=True) or {}
    try:
        interval = int(data.get("interval", 2))
    except (ValueError, TypeError):
        return jsonify({"error": "Intervalle invalide"}), 400

    if interval not in AVAILABLE_INTERVALS:
        return jsonify({"error": f"Intervalle non autorisé. Choisissez parmi : {AVAILABLE_INTERVALS}"}), 400

    config.NEWS_INTERVAL_HOURS = interval
    logger.info("Fréquence de mise à jour changée : toutes les %d heures", interval)
    return jsonify({"success": True, "interval": interval})


@app.route("/api/tweet-now", methods=["POST"])
def api_tweet_now():
    """
    API : génère une nouvelle breaking news et la publie sur Twitter.
    Retourne aussi la simulation visuelle du tweet pour validation.
    """
    # 1. Génération de la breaking news
    news = news_service.generate_breaking_news()
    if not news:
        return jsonify({"error": "Échec de la génération de la breaking news"}), 500

    # 2. Simulation visuelle du tweet
    tweet_preview = {
        "text": news["breaking_text"],
        "title": news["title"],
        "url": news["url"],
        "source": news["source"],
        "published_at": news["published_at"],
        "character_count": len(news["breaking_text"]),
    }

    # 3. Publication sur Twitter (si configuré et pas en dry-run)
    published = False
    if not config.DRY_RUN and config.TWITTER_API_KEY:
        try:
            twitter = twitter_client.TwitterClient()
            if twitter.configure():
                published = twitter.post_tweet(news["breaking_text"])
                logger.info("Tweet publié : %s", published)
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur lors de la publication Twitter : %s", exc)
    else:
        logger.info("Mode dry-run ou Twitter non configuré — tweet non publié réellement")

    return jsonify({
        "success": True,
        "news": news,
        "tweet_preview": tweet_preview,
        "published": published,
        "dry_run": config.DRY_RUN,
    })


@app.route("/api/twitter/status")
def api_twitter_status():
    """API : vérifie si Twitter est configuré."""
    configured = bool(config.TWITTER_API_KEY and config.TWITTER_API_SECRET)
    return jsonify({
        "configured": configured,
        "dry_run": config.DRY_RUN,
    })


@app.route("/api/twitter/connect", methods=["POST"])
def api_twitter_connect():
    """
    API : vérifie la connexion Twitter en testant la configuration.
    Retourne l'état de la connexion.
    """
    if not config.TWITTER_API_KEY or not config.TWITTER_API_SECRET:
        return jsonify({
            "success": False,
            "error": "Twitter n'est pas configuré. Renseignez TWITTER_API_KEY et TWITTER_API_SECRET dans .env",
        }), 400

    try:
        twitter = twitter_client.TwitterClient()
        if twitter.configure():
            return jsonify({
                "success": True,
                "message": "Connexion Twitter établie avec succès",
                "dry_run": config.DRY_RUN,
            })
        return jsonify({
            "success": False,
            "error": "Échec de la configuration Twitter. Vérifiez vos clés API.",
        }), 400
    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la connexion Twitter : %s", exc)
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la connexion Twitter : {exc}",
        }), 500


def run_web_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Lance le serveur web Flask."""
    logger.info("🚀 Serveur web démarré sur http://%s:%d", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    database.init_db()
    run_web_server()