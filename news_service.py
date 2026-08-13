"""
Service de Breaking News IA — scraping + génération + stockage.

Récupère les derniers articles IA & Tech via RSS, sélectionne les 3
meilleurs articles, génère un résumé "breaking news" avec l'IA pour
chacun, et les stocke en base pour affichage sur la page web.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import config
import database
import rss_parser
import ai_generator

logger = logging.getLogger(__name__)

# Nombre de propositions à générer (1 principale + 2 secondaires)
NUM_PROPOSALS = 3


def generate_breaking_news() -> Optional[dict]:
    """
    Génère une breaking news AI à partir des derniers articles RSS.

    :return: dict avec les infos de la news, ou None si échec
    """
    logger.info("=== Génération d'une breaking news AI ===")

    # 1. Récupération des articles RSS
    articles = rss_parser.fetch_articles(max_items=config.MAX_ARTICLES_TO_PROCESS)

    if not articles:
        logger.warning("Aucun article récupéré depuis les flux RSS.")
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
        breaking_text = ai_generator.generate_tweet(
            title=article.title,
            url=article.url,
            source=article.source,
            summary=article.summary,
        )

        if not breaking_text:
            logger.warning("Échec de la génération IA pour la proposition %d", i + 1)
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

    logger.info(
        "Breaking news générée et stockée : %s (+ %d propositions secondaires)",
        news["title"][:60],
        len(news["secondary_proposals"]),
    )
    return news


def get_latest_news() -> Optional[dict]:
    """Retourne la dernière breaking news stockée en base."""
    return database.get_latest_breaking_news()


def get_all_news(limit: int = 50) -> list:
    """Retourne l'historique des breaking news."""
    return database.get_breaking_news_history(limit=limit)