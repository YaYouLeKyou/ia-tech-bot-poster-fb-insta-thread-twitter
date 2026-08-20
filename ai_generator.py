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


def _create_llm_client() -> Optional[OpenAI]:
    """
    Crée un client OpenAI SDK pour le fournisseur LLM principal.
    """
    if not config.LLM_API_KEY:
        logger.error("LLM_API_KEY manquante dans l'environnement")
        return None
    return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def _create_groq_client() -> Optional[OpenAI]:
    """
    Crée un client OpenAI SDK pour Groq (fallback).
    """
    if not config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY manquante dans l'environnement")
        return None
    return OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)


def _call_llm_with_fallback(
    client: OpenAI,
    fallback_client: Optional[OpenAI],
    model: str,
    messages: list,
    max_tokens: int = 300,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Appelle l'API LLM avec fallback automatique sur Groq en cas de 429.
    """
    response = None
    used_fallback = False

    try:
        logger.info("Appel de l'IA (%s) pour générer le contenu…", model)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        error_str = str(exc)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            logger.warning("Quota/rate-limit atteint pour %s, tentative avec Groq…", model)
            if fallback_client and config.GROQ_API_KEY:
                try:
                    response = fallback_client.chat.completions.create(
                        model=config.GROQ_MODEL,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    used_fallback = True
                    logger.info("✅ Fallback Groq réussi (%s)", config.GROQ_MODEL)
                    return response.choices[0].message.content or ""
                except Exception as fallback_exc:  # noqa: BLE001
                    logger.error("Échec du fallback Groq : %s", fallback_exc)
            else:
                logger.error("Pas de fallback Groq configuré (GROQ_API_KEY manquant)")
        else:
            logger.error("Erreur lors de l'appel LLM : %s", exc)
    return None


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
    client = _create_llm_client()
    if not client:
        return None

    groq_client = _create_groq_client()

    prompt = config.AI_USER_PROMPT_TEMPLATE.format(
        title=title,
        source=source,
        url=url,
        summary=summary or "Pas de résumé disponible.",
        max_length=HARD_LIMIT,
    )

    raw_tweet = _call_llm_with_fallback(
        client=client,
        fallback_client=groq_client,
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": config.AI_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.7,
    )

    if not raw_tweet:
        logger.error("Échec de la génération du tweet après fallback")
        return None

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


def generate_french_title(title: str, source: str, summary: str = "") -> Optional[str]:
    """
    Génère un titre court en français à partir d'un article.

    :param title: Titre original de l'article
    :param source: Nom de la source
    :param summary: Résumé de l'article
    :return: Titre français (ou None si erreur)
    """
    client = _create_llm_client()
    if not client:
        return None

    groq_client = _create_groq_client()

    prompt = config.AI_TITLE_PROMPT_TEMPLATE.format(
        title=title,
        source=source,
        summary=summary or "Pas de résumé disponible.",
    )

    raw_title = _call_llm_with_fallback(
        client=client,
        fallback_client=groq_client,
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": config.AI_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=100,
        temperature=0.7,
    )

    if not raw_title:
        logger.error("Échec de la génération du titre français après fallback")
        return None

    french_title = _clean_generated_tweet(raw_title)

    if not french_title:
        logger.warning("Titre français vide généré pour : %s", title[:60])
        return None

    logger.info("Titre français généré : %s", french_title)
    return french_title


def generate_long_post(title: str, url: str, source: str, summary: str = "") -> Optional[str]:
    """
    Génère un post long en français pour Facebook/Instagram à partir d'un article.

    :param title: Titre de l'article
    :param url: Lien de l'article
    :param source: Nom de la source
    :param summary: Résumé de l'article
    :return: Post long prêt à publier (ou None si erreur)
    """
    client = _create_llm_client()
    if not client:
        return None

    groq_client = _create_groq_client()

    prompt = config.AI_LONG_POST_PROMPT_TEMPLATE.format(
        title=title,
        source=source,
        url=url,
        summary=summary or "Pas de résumé disponible.",
        max_length=config.MAX_LONG_POST_LENGTH,
    )

    raw_post = _call_llm_with_fallback(
        client=client,
        fallback_client=groq_client,
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": config.AI_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.7,
    )

    if not raw_post:
        logger.error("Échec de la génération du post long après fallback")
        return None

    long_post = _clean_generated_tweet(raw_post)

    # Force la présence du lien à la fin si l'IA ne l'a pas inclus
    if url not in long_post:
        if len(long_post) + len(url) + 2 > config.MAX_LONG_POST_LENGTH:
            long_post = long_post[: config.MAX_LONG_POST_LENGTH - len(url) - 3].rstrip() + "…"
        long_post = f"{long_post}\n{url}".strip()

    # Vérifie les hashtags — ajoute un fallback si absent
    if not re.search(r"#[\wéàèêâîôûç]+", long_post):
        hashtag = " #IA #Tech"
        if len(long_post) + len(hashtag) <= config.MAX_LONG_POST_LENGTH:
            long_post = f"{long_post}{hashtag}"

    # Troncature finale de sécurité
    if len(long_post) > config.MAX_LONG_POST_LENGTH:
        long_post = _truncate_tweet(long_post, url)

    logger.info("Post long généré : %d caractères", len(long_post))
    return long_post