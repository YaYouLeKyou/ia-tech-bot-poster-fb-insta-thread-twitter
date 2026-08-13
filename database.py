"""
Base de données SQLite locale — anti-doublons.

Stocke les liens d'articles déjà traités afin d'éviter
de republier la même actualité sur Twitter/X.
"""

import sqlite3
import logging
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Schéma de la table
# ─────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS processed_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    source TEXT,
    tweet_text TEXT,
    published_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection() -> sqlite3.Connection:
    """Retourne une connexion SQLite (avec vérification des clés étrangères)."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    """Initialise la base de données et crée la table si nécessaire."""
    conn = get_connection()
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        logger.info("Base de données initialisée : %s", config.DB_PATH)
    finally:
        conn.close()


def is_article_processed(url: str) -> bool:
    """
    Vérifie si un lien d'article a déjà été traité.

    :param url: URL canonique de l'article
    :return: True si déjà traité, False sinon
    """
    if not url:
        return False
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM processed_articles WHERE url = ? LIMIT 1",
            (url,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def mark_article_processed(
    url: str,
    title: str = "",
    source: str = "",
    tweet_text: str = "",
) -> None:
    """
    Enregistre un article comme traité dans la base.

    :param url: URL canonique de l'article (clé unique)
    :param title: Titre de l'article
    :param source: Nom de la source RSS
    :param tweet_text: Texte du tweet généré / publié
    """
    conn = get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO processed_articles
                (url, title, source, tweet_text, published_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (url, title, source, tweet_text, now, now),
        )
        conn.commit()
        logger.info("Article enregistré comme traité : %s", url)
    except sqlite3.IntegrityError as exc:
        logger.warning("Article déjà présent en base (ignoré) : %s — %s", url, exc)
    finally:
        conn.close()


def get_statistics() -> dict:
    """
    Retourne des statistiques simples sur la base.

    :return: dict avec count, last_processed_at
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) AS count, MAX(published_at) AS last FROM processed_articles"
        )
        row = cursor.fetchone()
        return {
            "count": row["count"] if row else 0,
            "last_processed_at": row["last"] if row else None,
        }
    finally:
        conn.close()