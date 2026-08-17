"""
Application Web — Affichage des Breaking News AI.

Sert une page web qui affiche la dernière breaking news générée
par le scraper, avec :
  - Choix de la fréquence de mise à jour (2h, 4h, 8h... 48h)
  - Bouton "Tweet Now" pour publier en direct
  - Simulation visuelle du tweet pour validation
"""

import logging
import re
from datetime import datetime, timezone

import schedule
from flask import Flask, jsonify, render_template, request

import config
import database
import facebook_client
import news_service
import twitter_client

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Fréquences disponibles (en heures)
# 0 = désactivé (publication uniquement aux heures planifiées)
AVAILABLE_INTERVALS = [0, 2, 4, 6, 8, 12, 24, 48]


def _scheduled_publish() -> None:
    """
    Tâche planifiée : génère une breaking news et la publie sur
    Twitter + Facebook (respecte DRY_RUN via les clients).
    """
    logger.info("=== Publication planifiée d'une breaking news ===")
    news = news_service.generate_breaking_news()
    if not news:
        logger.warning("⚠️  Échec de la génération de la breaking news planifiée")
        return

    logger.info("✅ Breaking news générée : %s", news["title"][:60])

    # Publication Twitter
    if config.TWITTER_API_KEY and config.TWITTER_API_SECRET:
        try:
            twitter = twitter_client.TwitterClient()
            if twitter.configure():
                twitter.post_tweet(news["breaking_text"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur publication Twitter (planifiée) : %s", exc)
    else:
        logger.warning("Twitter non configuré — tweet planifié non publié")

    # Publication Facebook
    if config.FB_PAGE_ACCESS_TOKEN and config.FACEBOOK_PAGE_ID:
        try:
            facebook = facebook_client.FacebookClient()
            if facebook.configure():
                facebook.post_to_page(message=news["breaking_text"], link=news.get("url", ""))
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur publication Facebook (planifiée) : %s", exc)
    else:
        logger.warning("Facebook non configuré — post planifié non publié")

    # Publication Instagram
    if config.FB_PAGE_ACCESS_TOKEN and config.INSTAGRAM_ACCOUNT_ID:
        try:
            facebook = facebook_client.FacebookClient()
            if facebook.configure():
                facebook.post_to_instagram(message=news["breaking_text"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur publication Instagram (planifiée) : %s", exc)
    else:
        logger.warning("Instagram non configuré — post planifié non publié")


def _reschedule() -> None:
    """Re-planifie les publications selon config.SCHEDULE_TIMES."""
    schedule.clear()
    for time_str in config.SCHEDULE_TIMES:
        schedule.every().day.at(time_str).do(_scheduled_publish)
        logger.info("Publication planifiée : %s UTC", time_str)


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
    schedule_times = config.SCHEDULE_TIMES

    # Vérifie si les réseaux sont configurés
    twitter_configured = bool(config.TWITTER_API_KEY and config.TWITTER_API_SECRET)
    facebook_configured = bool(config.FB_PAGE_ACCESS_TOKEN and config.FACEBOOK_PAGE_ID)
    instagram_configured = bool(config.FB_PAGE_ACCESS_TOKEN and config.INSTAGRAM_ACCOUNT_ID)
    threads_configured = bool(config.THREADS_ACCESS_TOKEN and config.THREADS_USER_ID)

    return render_template(
        "index.html",
        latest=latest,
        history=history,
        stats=stats,
        now=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        available_intervals=AVAILABLE_INTERVALS,
        current_interval=current_interval,
        schedule_times=schedule_times,
        twitter_configured=twitter_configured,
        facebook_configured=facebook_configured,
        instagram_configured=instagram_configured,
        threads_configured=threads_configured,
        dry_run=config.DRY_RUN,
        test_on_startup=config.TEST_ON_STARTUP,
        max_history_size=config.MAX_HISTORY_SIZE,
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


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """
    API JSON : force la génération d'une nouvelle breaking news.
    Filtre les articles déjà traités pour toujours renvoyer du contenu neuf.
    """
    news = news_service.generate_breaking_news(force=True)
    if not news:
        latest = news_service.get_latest_news()
        if latest:
            return jsonify({
                "success": False,
                "error": "Aucun nouvel article disponible.",
                "message": "Tous les articles RSS ont déjà été publiés. "
                           "Patientez jusqu'à de nouveaux articles, ou "
                           "effacez l'historique pour tout republier.",
                "latest_title": latest["title"][:50],
            }), 409
        return jsonify({
            "error": "Échec de la génération d'article.",
            "detail": "Tous les flux RSS ont été épuisés ou inaccessible.",
        }), 404
    return jsonify(news)


@app.route("/api/refresh-proposal")
def api_refresh_proposal():
    """
    API JSON : génère une seule proposition secondaire (article non traité).
    Utilisé par le bouton 🔄 des cartes "Autres propositions".
    """
    proposal = news_service.generate_proposal()
    if not proposal:
        latest = news_service.get_latest_news()
        if latest:
            return jsonify({
                "success": False,
                "error": "Aucun nouvel article disponible.",
                "message": "Tous les articles RSS ont déjà été publiés. "
                           "Patientez jusqu'à de nouveaux articles, ou "
                           "effacez l'historique pour tout republier.",
                "latest_title": latest["title"][:50],
            }), 409
        return jsonify({
            "error": "Échec de la génération de la proposition.",
            "detail": "Tous les flux RSS ont été épuisés ou inaccessible.",
        }), 404
    return jsonify(proposal)


@app.route("/api/clear-history", methods=["POST"])
def api_clear_history():
    """API : vide l'historique des breaking news et le cache anti-doublons."""
    removed_news = database.clear_breaking_news_history()
    removed_processed = database.clear_processed_articles()
    logger.info(
        "Historique vidé : %d breaking news, %d articles traités supprimés",
        removed_news,
        removed_processed,
    )
    return jsonify({
        "success": True,
        "message": "Historique effacé avec succès.",
        "removed_news": removed_news,
        "removed_processed": removed_processed,
    })


@app.route("/api/interval", methods=["POST"])
def api_set_interval():
    """API : change la fréquence de mise à jour (en heures). 0 = désactivé."""
    data = request.get_json(silent=True) or {}
    try:
        interval = int(data.get("interval", 2))
    except (ValueError, TypeError):
        return jsonify({"error": "Intervalle invalide"}), 400

    if interval not in AVAILABLE_INTERVALS:
        return jsonify({"error": f"Intervalle non autorisée. Choisissez parmi : {AVAILABLE_INTERVALS}"}), 400

    config.NEWS_INTERVAL_HOURS = interval
    logger.info("Fréquence de mise à jour changée : %s", "désactivée" if interval == 0 else f"toutes les {interval} heures")
    return jsonify({"success": True, "interval": interval, "label": "Désactivé" if interval == 0 else f"Toutes les {interval} heures"})


@app.route("/api/schedule", methods=["POST"])
def api_set_schedule():
    """
    API : change les heures de publication planifiées (format HH:MM, UTC).
    Re-planifie immédiatement les publications.
    """
    data = request.get_json(silent=True) or {}
    raw_times = data.get("times", [])

    # Validation du format HH:MM
    valid_times = []
    for t in raw_times:
        t = str(t).strip()
        if re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t):
            valid_times.append(t)

    if not valid_times:
        return jsonify({
            "error": "Aucune heure valide. Format attendu : HH:MM (ex: 08:30, 17:30)",
        }), 400

    # Mise à jour de la configuration et re-planification
    config.SCHEDULE_TIMES = valid_times
    _reschedule()
    logger.info("Heures de publication mises à jour : %s UTC", valid_times)
    return jsonify({"success": True, "times": valid_times})


@app.route("/api/tweet-now", methods=["POST"])
def api_tweet_now():
    """
    API : génère une nouvelle breaking news et la publie sur les
    plateformes sélectionnées : twitter, facebook, instagram, threads.
    Retourne la simulation visuelle et le statut de publication.
    """
    data = request.get_json(silent=True) or {}
    raw_network = data.get("network", "facebook")
    if isinstance(raw_network, str):
        networks = [n.strip() for n in raw_network.split(",") if n.strip()]
    else:
        networks = [str(raw_network)]

    valid_networks = [n for n in networks if n in ("twitter", "facebook", "instagram", "threads")]
    if not valid_networks:
        valid_networks = ["facebook"]

    post_twitter = "twitter" in valid_networks
    post_facebook = "facebook" in valid_networks
    post_instagram = "instagram" in valid_networks
    post_threads = "threads" in valid_networks

    progress = []
    result = {
        "success": True,
        "network": ",".join(valid_networks),
        "progress": progress,
    }

    # 1. Génération de la breaking news
    news = news_service.generate_breaking_news(force=True)
    if not news:
        latest = news_service.get_latest_news()
        if latest:
            return jsonify({
                "error": "Article déjà publié récemment.",
                "detail": "La dernière breaking news a déjà été publiée. Patientez jusqu'à de nouveaux articles RSS.",
                "latest_title": latest["title"][:50],
            }), 409
        return jsonify({"error": "Aucun article disponible."}), 404

    progress.append({"step": "generation", "message": "Article généré avec succès", "done": True})

    # 2. Simulation visuelle du tweet
    tweet_preview = {
        "text": news["breaking_text"],
        "title": news["title"],
        "url": news["url"],
        "source": news["source"],
        "published_at": news["published_at"],
        "character_count": len(news["breaking_text"]),
    }
    result["tweet_preview"] = tweet_preview
    result["news"] = news

    # 3. Publication sur Twitter (seulement si explicitement demandé)
    published = False
    free_mode = False
    if post_twitter:
        progress.append({"step": "twitter", "message": "Envoi du post Twitter…", "done": False})
        if not config.DRY_RUN and config.TWITTER_API_KEY:
            try:
                twitter = twitter_client.TwitterClient()
                if twitter.configure():
                    published = twitter.post_tweet(news["breaking_text"])
                    free_mode = twitter._credits_depleted
                    logger.info("Tweet publié : %s (mode gratuit : %s)", published, free_mode)
                    progress[-1]["done"] = True
                    progress[-1]["success"] = published
                else:
                    progress[-1]["done"] = True
                    progress[-1]["success"] = False
                    progress[-1]["error"] = "Twitter non configuré"
            except Exception as exc:  # noqa: BLE001
                logger.error("Erreur lors de la publication Twitter : %s", exc)
                progress[-1]["done"] = True
                progress[-1]["success"] = False
                progress[-1]["error"] = str(exc)
        else:
            progress[-1]["done"] = True
            progress[-1]["success"] = False
            progress[-1]["error"] = "Mode dry-run ou Twitter non configuré"
    else:
        # Twitter désactivé par défaut
        if network == "all":
            progress.append({"step": "twitter", "message": "Twitter désactivé par défaut", "done": True, "skipped": True})

    result["published"] = published
    result["free_mode"] = free_mode

    # 4. Publication sur Facebook (seulement si explicitement demandé)
    facebook_published = False
    facebook_error = None
    if post_facebook:
        progress.append({"step": "facebook", "message": "Envoi du post Facebook…", "done": False})
        if not config.DRY_RUN and config.FB_PAGE_ACCESS_TOKEN and config.FACEBOOK_PAGE_ID:
            try:
                facebook = facebook_client.FacebookClient()
                if facebook.configure():
                    facebook_published = facebook.post_to_page(
                        message=news["breaking_text"],
                        link=news.get("url", ""),
                    )
                    logger.info("Post Facebook publié : %s", facebook_published)
                    progress[-1]["done"] = True
                    progress[-1]["success"] = facebook_published
                    if not facebook_published:
                        facebook_error = "Échec de la publication Facebook — voir les logs serveur"
                        progress[-1]["error"] = facebook_error
                else:
                    facebook_error = (
                        "Token Facebook/Instagram expiré ou invalide. "
                        "Générez un nouveau Page Access Token sur "
                        "https://developers.facebook.com/tools/access-token/ "
                        "avec les permissions pages_read_engagement et pages_manage_posts, "
                        "puis redémarrez l'application."
                    )
                    progress[-1]["done"] = True
                    progress[-1]["success"] = False
                    progress[-1]["error"] = facebook_error
            except Exception as exc:  # noqa: BLE001
                logger.error("Erreur lors de la publication Facebook : %s", exc)
                facebook_error = str(exc)
                progress[-1]["done"] = True
                progress[-1]["success"] = False
                progress[-1]["error"] = facebook_error
        else:
            progress[-1]["done"] = True
            progress[-1]["success"] = False
            if config.DRY_RUN:
                progress[-1]["error"] = "Mode dry-run activé"
            elif not config.FB_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
                progress[-1]["error"] = "Facebook non configuré"
    else:
        progress.append({"step": "facebook", "message": "Facebook non sélectionné", "done": True, "skipped": True})

    result["facebook_published"] = facebook_published
    result["facebook_error"] = facebook_error

    # 5. Publication sur Instagram (seulement si explicitement demandé)
    instagram_published = False
    instagram_error = None
    if post_instagram:
        progress.append({"step": "instagram", "message": "Envoi du post Instagram…", "done": False})
        if not config.DRY_RUN and config.FB_PAGE_ACCESS_TOKEN and config.INSTAGRAM_ACCOUNT_ID:
            try:
                facebook = facebook_client.FacebookClient()
                if facebook.configure():
                    instagram_image = news.get("url", "")
                    instagram_published = facebook.post_to_instagram(
                        message=news["breaking_text"],
                        image_url=instagram_image,
                    )
                    logger.info("Post Instagram publié : %s", instagram_published)
                    progress[-1]["done"] = True
                    progress[-1]["success"] = instagram_published
                    if not instagram_published:
                        instagram_error = "Échec de la publication Instagram — voir les logs serveur"
                        progress[-1]["error"] = instagram_error
                else:
                    instagram_error = (
                        "Token Instagram expiré ou invalide. "
                        "Générez un nouveau Page Access Token sur "
                        "https://developers.facebook.com/tools/access-token/ "
                        "avec les permissions pages_read_engagement et pages_manage_posts, "
                        "puis redémarrez l'application."
                    )
                    progress[-1]["done"] = True
                    progress[-1]["success"] = False
                    progress[-1]["error"] = instagram_error
            except Exception as exc:  # noqa: BLE001
                logger.error("Erreur lors de la publication Instagram : %s", exc)
                instagram_error = str(exc)
                progress[-1]["done"] = True
                progress[-1]["success"] = False
                progress[-1]["error"] = instagram_error
        else:
            progress[-1]["done"] = True
            progress[-1]["success"] = False
            if config.DRY_RUN:
                progress[-1]["error"] = "Mode dry-run activé"
            elif not config.INSTAGRAM_ACCOUNT_ID:
                progress[-1]["error"] = "Instagram non configuré"
    else:
        progress.append({"step": "instagram", "message": "Instagram non sélectionné", "done": True, "skipped": True})

    result["instagram_published"] = instagram_published
    result["instagram_error"] = instagram_error

    # 6. Publication sur Threads (seulement si explicitement demandé)
    threads_published = False
    threads_error = None
    if post_threads:
        progress.append({"step": "threads", "message": "Envoi du post Threads…", "done": False})
        if not config.DRY_RUN and config.THREADS_ACCESS_TOKEN and config.THREADS_USER_ID:
            try:
                facebook = facebook_client.FacebookClient()
                if facebook.configure():
                    threads_published = facebook.post_to_threads(
                        message=news["breaking_text"],
                    )
                    logger.info("Post Threads publié : %s", threads_published)
                    progress[-1]["done"] = True
                    progress[-1]["success"] = threads_published
                    if not threads_published:
                        threads_error = "Échec de la publication Threads — voir les logs serveur"
                        progress[-1]["error"] = threads_error
                else:
                    threads_error = (
                        "Token Threads expiré ou invalide. "
                        "Générez un nouveau Threads Access Token sur "
                        "https://developers.facebook.com/tools/access-token/ "
                        "avec les permissions threads_basic et threads_content_publish, "
                        "puis redémarrez l'application."
                    )
                    progress[-1]["done"] = True
                    progress[-1]["success"] = False
                    progress[-1]["error"] = threads_error
            except Exception as exc:  # noqa: BLE001
                logger.error("Erreur lors de la publication Threads : %s", exc)
                threads_error = str(exc)
                progress[-1]["done"] = True
                progress[-1]["success"] = False
                progress[-1]["error"] = threads_error
        else:
            progress[-1]["done"] = True
            progress[-1]["success"] = False
            if config.DRY_RUN:
                progress[-1]["error"] = "Mode dry-run activé"
            elif not config.THREADS_USER_ID or not config.THREADS_ACCESS_TOKEN:
                progress[-1]["error"] = "Threads non configuré"
    else:
        progress.append({"step": "threads", "message": "Threads non sélectionné", "done": True, "skipped": True})

    result["threads_published"] = threads_published
    result["threads_error"] = threads_error
    result["dry_run"] = config.DRY_RUN

    # Message final de progression
    if post_facebook or post_threads or post_twitter or post_instagram:
        has_success = (post_facebook and facebook_published) or (post_threads and threads_published) or (post_twitter and published) or (post_instagram and instagram_published)
        if has_success:
            progress.append({"step": "done", "message": "Publication terminée avec succès !", "done": True, "final": True})
        else:
            progress.append({"step": "done", "message": "Publication terminée (partielle)", "done": True, "final": True})
    else:
        progress.append({"step": "done", "message": "Publication échouée", "done": True, "final": True, "error": True})

    return jsonify(result)


@app.route("/api/twitter/status")
def api_twitter_status():
    """API : vérifie si Twitter est configuré."""
    configured = bool(config.TWITTER_API_KEY and config.TWITTER_API_SECRET)
    return jsonify({
        "configured": configured,
        "dry_run": config.DRY_RUN,
    })


@app.route("/api/facebook/status")
def api_facebook_status():
    """API : vérifie si Facebook est configuré."""
    configured = bool(config.FB_PAGE_ACCESS_TOKEN and config.FACEBOOK_PAGE_ID)
    return jsonify({
        "configured": configured,
        "dry_run": config.DRY_RUN,
    })


@app.route("/api/facebook/connect", methods=["POST"])
def api_facebook_connect():
    """
    API : vérifie la connexion Facebook en testant la configuration.
    Retourne l'état de la connexion et les infos de la page.
    """
    if not config.FB_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        return jsonify({
            "success": False,
            "error": "Facebook n'est pas configuré. Renseignez FB_PAGE_ACCESS_TOKEN et FACEBOOK_PAGE_ID dans .env",
        }), 400

    try:
        facebook = facebook_client.FacebookClient()
        if facebook.configure(verify_token=True):
            page_info = facebook.get_page_info()
            return jsonify({
                "success": True,
                "message": "Connexion Facebook établie avec succès",
                "page_name": page_info.get("name") if page_info else None,
                "page_fans": page_info.get("fan_count") if page_info else None,
                "dry_run": config.DRY_RUN,
            })
        return jsonify({
            "success": False,
            "error": "Token Facebook invalide ou expiré (code 190/467). "
                     "Générez un nouveau Page Access Token sur "
                     "https://developers.facebook.com/tools/access-token/ "
                     "avec les permissions pages_read_engagement et pages_manage_posts.",
        }), 400
    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la connexion Facebook : %s", exc)
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la connexion Facebook : {exc}",
        }), 500


@app.route("/api/facebook/diagnostic")
def api_facebook_diagnostic():
    """
    API : diagnostic complet du token Facebook.
    Vérifie la validité du token et les permissions via /debug_token.
    """
    if not config.FB_PAGE_ACCESS_TOKEN:
        return jsonify({
            "success": False,
            "error": "FB_PAGE_ACCESS_TOKEN non configuré dans .env",
        }), 400

    facebook = facebook_client.FacebookClient()
    token_info = facebook.check_token()

    if token_info is None:
        return jsonify({
            "success": False,
            "error": "Erreur réseau lors de la vérification du token Meta",
        }), 500

    return jsonify({
        "success": True,
        "token_info": token_info,
        "page_id": config.FACEBOOK_PAGE_ID,
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