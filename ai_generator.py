"""
Générateur IA de tweets — DeepSeek / OpenAI (SDK OpenAI compatible).

Transforme un article RSS en tweet optimisé en français,
avec 2 hashtags ciblés et un ton journalistique expert Tech/IA.
"""

import logging
import re
from typing import Optional

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# Limite stricte imposée à l'IA (marge de sécurité sous les 280)
HARD_LIMIT = config.MAX_TWEET_LENGTH


def _truncate_tweet(text: str, url: str) -> str:
    """
    Tronque proprement un tweet trop long en conservant la fin (lien + hashtags).

    Stratégie : si le texte dépasse la limite, on coupe le milieu
    en conservant le début (accroche) et la fin (lien + hashtags).
    """
    if len(text) <= HARD_LIMIT:
        return text

    logger.warning("Tweet généré trop long (%d caractères) — troncature", len(text))

    # Taille des éléments de fin à préserver
    url_len = len(url) + 1
    suffix_needed = url_len + 30  # hashtags + espace de respiration

    head_len = max(60, HARD_LIMIT - suffix_needed)
    head = text[:head_len].rstrip()
    tail = text[-suffix_needed:].lstrip()

    # Ajout d'une ellipse de séparation
    truncated = f"{head}… {tail}"

    if len(truncated) > HARD_LIMIT:
        truncated = truncated[: HARD_LIMIT - 1].rstrip() + "…"

    return truncated


def _clean_generated_tweet(raw: str) -> str:
    """Nettoie la réponse de l'IA (guillemets parasites, retours à la ligne)."""
    text = raw.strip()
    # Retire les guillemets ouvrants/fermants si l'IA a encadré le tweet
    if len(text) >= 2 and text[0] in ('"', "'", "«") and text[-1] in ('"', "'", "»"):
        text = text[1:-1].strip()
    # Remplace les retours à la ligne par des espaces
    text = re.sub(r"\s+", " ", text)
    return text


def generate_tweet(title: str, url: str, source: str, summary: str = "") -> Optional[str]:
    """
    Génère un tweet en français à partir d'un article.

    :param title: Titre de l'article
    :param url: Lien de l'article
    :param source: Nom de la source
    :param summary: Résumé de l'article
    :return: Tweet prêt à publier (ou None si erreur)
    """
    if not config.LLM_API_KEY:
        logger.error("LLM_API_KEY manquante dans l'environnement")
        return None

    prompt = config.AI_USER_PROMPT_TEMPLATE.format(
        title=title,
        source=source,
        url=url,
        summary=summary or "Pas de résumé disponible.",
        max_length=HARD_LIMIT,
    )

    try:
        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)

        logger.info("Appel de l'IA (%s) pour générer le tweet…", config.LLM_MODEL)
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": config.AI_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        raw_tweet = response.choices[0].message.content or ""
        tweet = _clean_generated_tweet(raw_tweet)

        # Force la présence du lien à la fin si l'IA ne l'a pas inclus
        if url not in tweet:
            if len(tweet) + len(url) + 2 > HARD_LIMIT:
                tweet = _truncate_tweet(tweet, url)
            tweet = f"{tweet}\n{url}".strip()

        # Vérifie les hashtags — ajoute un fallback #IA si absent
        if not re.search(r"#[\wéàèêâîôûç]+", tweet):
            hashtag = " #IA"
            if len(tweet) + len(hashtag) <= HARD_LIMIT:
                tweet = f"{tweet}{hashtag}"
            else:
                tweet = _truncate_tweet(tweet + hashtag, url)

        # Troncature finale de sécurité
        if len(tweet) > HARD_LIMIT:
            tweet = _truncate_tweet(tweet, url)

        logger.info("Tweet généré : %d caractères", len(tweet))
        return tweet

    except Exception as exc:  # noqa: BLE001
        logger.error("Erreur lors de la génération IA : %s", exc)
        return None