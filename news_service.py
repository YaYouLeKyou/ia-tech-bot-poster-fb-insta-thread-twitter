"""
Service de Breaking News IA — scraping + génération + stockage.

Récupère les derniers articles IA & Tech via RSS, sélectionne les 3
meilleurs articles, génère un résumé "breaking news" avec l'IA pour
chacun, et les stocke en base pour affichage sur la page web.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import config
import database
import rss_parser
import ai_generator

logger = logging.getLogger(__name__)

# Nombre de propositions à générer (1 principale + 2 secondaires)
NUM_PROPOSALS = 3

# Verrou pour empêcher l'exécution concurrente de generate_breaking_news().
# Sans cela, un appel via /api/tweet-now peut se superposer à un job planifié,
# entraînant des scans RSS parallèles et des doublons dans la base.
_breaking_news_lock = threading.Lock()


def generate_breaking_news(force: bool = False) -> Optional[dict]:
    """
    Génère une breaking news AI à partir des derniers articles RSS.

    :param force: Si True, récupère tous les articles puis filtre ceux déjà
                  traités pour éviter de régénérer les mêmes breaking news.
                  Si False, ne récupère que les articles non encore traités.
    :return: dict avec les infos de la news, ou None si échec
    """
    logger.info("=== Génération d'une breaking news AI (force=%s) ===", force)

    # Empêche l'exécution concurrente (superposition job planifié + API)
    if not _breaking_news_lock.acquire(blocking=False):
        logger.warning(
            "Génération de breaking news déjà en cours — appel ignoré. "
            "Attendez que le cycle précédent se termine."
        )
        return None

    try:
        # 1. Récupération des articles RSS
        if force:
            # Mode force : récupère tous les articles puis filtre ceux déjà
            # traités (anti-doublons), pour que chaque clic sur "Actualiser"
            # génère des propositions réellement nouvelles.
            all_articles = rss_parser.fetch_articles(max_items=config.MAX_ARTICLES_TO_PROCESS)
            articles = [
                article for article in all_articles
                if not database.is_article_processed(article.url)
            ]
            logger.info(
                "Mode force : %d articles récupérés, %d non encore traités",
                len(all_articles),
                len(articles),
            )
        else:
            # Mode normal : seulement les nouveaux articles non encore traités
            articles = rss_parser.fetch_new_articles(max_items=config.MAX_ARTICLES_TO_PROCESS)

        if not articles:
            logger.warning("Aucun nouvel article récupéré depuis les flux RSS.")
            return None

        # 2. Sélection des 3 meilleurs articles (les plus récents)
        best_articles = articles[:NUM_PROPOSALS]
        logger.info(
            "Articles sélectionnés : %d (le plus récent : « %s »)",
            len(best_articles),
            best_articles[0].title[:60],
        )

        # 3. Génération des résumés "breaking news" par l'IA pour chaque article
        proposals = []
        for i, article in enumerate(best_articles):
            if i > 0:
                # Espace les appels API pour respecter les limites TPM de Groq
                delay = config.AI_GENERATION_DELAY
                logger.info(
                    "Pause de %ds entre les générations IA…", delay
                )
                time.sleep(delay)

            breaking_text = ai_generator.generate_tweet(
                title=article.title,
                url=article.url,
                source=article.source,
                summary=article.summary,
            )

            if not breaking_text:
                logger.warning("Échec de la génération IA pour la proposition %d", i + 1)
                # Marque l'article comme traité pour ne pas bloquer indéfiniment
                database.mark_article_processed(
                    url=article.url,
                    title=article.title,
                    source=article.source,
                    tweet_text="",
                )
                continue

            proposals.append({
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "summary": article.summary,
                "breaking_text": breaking_text,
            })

        if not proposals:
            logger.error("Aucune proposition générée par l'IA.")
            return None

        # 4. Construction de l'objet news (principale + secondaires)
        now = datetime.now(timezone.utc).isoformat()
        news = {
            "title": proposals[0]["title"],
            "url": proposals[0]["url"],
            "source": proposals[0]["source"],
            "summary": proposals[0]["summary"],
            "breaking_text": proposals[0]["breaking_text"],
            "published_at": now,
            "secondary_proposals": proposals[1:],
        }

        # 5. Stockage en base
        database.save_breaking_news(news)

        # 5b. Élague l'historique si la taille maximale est dépassée
        database.enforce_max_history(config.MAX_HISTORY_SIZE)

        # 6. Marque tous les articles traités comme "déjà publiés" (anti-doublons)
        for proposal in proposals:
            database.mark_article_processed(
                url=proposal["url"],
                title=proposal["title"],
                source=proposal["source"],
                tweet_text=proposal["breaking_text"],
            )

        logger.info(
            "Breaking news générée et stockée : %s (+ %d propositions secondaires)",
            news["title"][:60],
            len(news["secondary_proposals"]),
        )
        return news
    finally:
        _breaking_news_lock.release()


def generate_proposal() -> Optional[dict]:
    """
    Génère une seule proposition secondaire à partir du prochain article
    RSS non encore traité (anti-doublons).

    Utilisé par le bouton 🔄 des cartes "Autres propositions" pour
    rafraîchir une proposition sans régénérer toute la breaking news.

    :return: dict avec title, url, source, summary, breaking_text,
             ou None si aucun article disponible
    """
    logger.info("=== Génération d'une proposition secondaire ===")

    if not _breaking_news_lock.acquire(blocking=False):
        logger.warning(
            "Génération de breaking news déjà en cours — proposition ignorée. "
            "Attendez que le cycle précédent se termine."
        )
        return None

    try:
        # Récupère tous les articles et filtre ceux déjà traités
        all_articles = rss_parser.fetch_articles(max_items=config.MAX_ARTICLES_TO_PROCESS)
        new_articles = [
            article for article in all_articles
            if not database.is_article_processed(article.url)
        ]

        if not new_articles:
            logger.warning("Aucun nouvel article disponible pour une proposition.")
            return None

        # Prend l'article le plus récent non traité
        article = new_articles[0]

        # Génère le résumé "breaking news" par l'IA
        breaking_text = ai_generator.generate_tweet(
            title=article.title,
            url=article.url,
            source=article.source,
            summary=article.summary,
        )

        if not breaking_text:
            logger.warning("Échec de la génération IA pour la proposition.")
            return None

        proposal = {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "summary": article.summary,
            "breaking_text": breaking_text,
        }

        # Marque l'article comme traité (anti-doublons)
        database.mark_article_processed(
            url=article.url,
            title=article.title,
            source=article.source,
            tweet_text=breaking_text,
        )

        logger.info("Proposition générée : %s", article.title[:60])
        return proposal
    finally:
        _breaking_news_lock.release()


def get_latest_news() -> Optional[dict]:
    """Retourne la dernière breaking news stockée en base."""
    return database.get_latest_breaking_news()


def get_all_news(limit: int = 50) -> list:
    """Retourne l'historique des breaking news."""
    return database.get_breaking_news_history(limit=limit)