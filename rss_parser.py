"""
Parseur de flux RSS — extraction des derniers articles IA & Tech.

Utilise la bibliothèque `feedparser` pour récupérer les articles
des flux configurés dans `config.RSS_FEEDS`.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import feedparser

import config

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Représente un article extrait d'un flux RSS."""

    title: str
    url: str
    source: str
    summary: str = ""
    published: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        """Un article est valide s'il a un titre et une URL."""
        return bool(self.title and self.url)


def _parse_date(published_parsed: tuple) -> Optional[datetime]:
    """Convertit la structure de date de feedparser en datetime UTC."""
    if not published_parsed:
        return None
    try:
        import calendar

        timestamp = calendar.timegm(published_parsed)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def _clean_summary(raw_summary: str) -> str:
    """Nettoie le résumé HTML en texte simple (premières phrases)."""
    if not raw_summary:
        return ""
    # Retire les balises HTML simples
    import re

    text = re.sub(r"<[^>]+>", " ", raw_summary)
    text = re.sub(r"\s+", " ", text).strip()
    # Limite à ~300 caractères
    return text[:300]


def fetch_articles(max_items: int = None) -> List[Article]:
    """
    Récupère les derniers articles de tous les flux RSS configurés.

    :param max_items: Nombre maximum d'articles à collecter au total
    :return: Liste d'articles triés par date de publication (récent → ancien)
    """
    max_items = max_items or config.MAX_ARTICLES_TO_PROCESS
    articles: List[Article] = []

    for feed_url in config.RSS_FEEDS:
        try:
            logger.info("Scan du flux RSS : %s", feed_url)
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(
                    "Flux invalide ou vide : %s — erreur : %s",
                    feed_url,
                    getattr(feed, "bozo_exception", "inconnue"),
                )
                continue

            source_name = feed.feed.get("title", feed_url) if hasattr(feed, "feed") else feed_url

            for entry in feed.entries[: max_items]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                summary = _clean_summary(entry.get("summary", ""))
                published = _parse_date(entry.get("published_parsed"))

                article = Article(
                    title=title,
                    url=url,
                    source=source_name,
                    summary=summary,
                    published=published,
                )
                if article.is_valid:
                    articles.append(article)

            logger.info("Flux %s : %d articles récupérés", feed_url, len(feed.entries[: max_items]))

        except Exception as exc:  # noqa: BLE001 — un flux ne doit pas bloquer les autres
            logger.error("Erreur lors du scan du flux %s : %s", feed_url, exc)

    # Tri : plus récent d'abord, les articles sans date en dernier
    articles.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    logger.info("Total : %d articles collectés depuis %d flux", len(articles), len(config.RSS_FEEDS))
    return articles


def fetch_new_articles(max_items: int = None) -> List[Article]:
    """
    Récupère les nouveaux articles non encore traités (anti-doublons).

    :param max_items: Nombre maximum d'articles à collecter
    :return: Liste d'articles non encore présents dans la base SQLite
    """
    from database import is_article_processed

    all_articles = fetch_articles(max_items=max_items)
    new_articles = [
        article for article in all_articles if not is_article_processed(article.url)
    ]
    logger.info("%d nouveaux articles (non encore publiés)", len(new_articles))
    return new_articles