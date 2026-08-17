"""
Générateur IA de tweets — Gemini (principal) / Groq (fallback).

Transforme un article RSS en tweet optimisé en français,
avec 2 hashtags ciblés et un ton journalistique expert Tech/IA.

Stratégie :
  1. Gemini (gratuit, fiable, tweet complet avec max_tokens=2000) — principal
  2. Groq (fallback) — si Gemini est indisponible ou rate-limité
"""

import logging
import re
import time
from typing import Optional

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# Limite stricte imposée à l'IA (marge de sécurité sous les 280)
HARD_LIMIT = config.MAX_TWEET_LENGTH

# Nombre maximal de tentatives en cas de rate limit (429)
MAX_RETRIES = 5
# Délai de base pour le backoff exponentiel (en secondes)
RETRY_BASE_DELAY = 5


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


def _is_rate_limited(exc: Exception) -> bool:
    """Vérifie si l'exception est un rate limit (HTTP 429)."""
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "rate_limit" in text


def _generate_with_client(
    client: OpenAI,
    model: str,
    provider_name: str,
    prompt: str,
    title: str,
    url: str,
) -> Optional[str]:
    """
    Tente de générer un tweet avec un client OpenAI-compatible donné.

    :param client: Client OpenAI configuré
    :param model: Nom du modèle
    :param provider_name: Nom du fournisseur (pour les logs)
    :param prompt: Prompt utilisateur
    :param title: Titre de l'article (pour les logs)
    :param url: Lien de l'article
    :return: Tweet prêt à publier, ou None si échec
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Appel de l'IA (%s via %s) pour générer le tweet… (tentative %d/%d)",
                model, provider_name, attempt, MAX_RETRIES,
            )
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": config.AI_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=config.LLM_MAX_TOKENS,
            )

            raw_tweet = response.choices[0].message.content or ""
            tweet = _clean_generated_tweet(raw_tweet)

            # Force la présence du lien à la fin si l'IA ne l'a pas inclus
            if url not in tweet:
                if len(tweet) + len(url) + 2 > HARD_LIMIT:
                    tweet = _truncate_tweet(tweet, url)
                tweet = f"{tweet}\n{url}".strip()

            # Vérifie que le tweet contient du contenu réel (pas seulement le lien)
            tweet_without_url = tweet.replace(url, "").strip()
            if len(tweet_without_url) < 20:
                logger.warning(
                    "Réponse IA vide ou quasi vide (contenu sans lien : %d caractères) "
                    "— nouvelle tentative %d/%d",
                    len(tweet_without_url), attempt, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.info("Attente de %ds avant nouvelle tentative…", wait)
                    time.sleep(wait)
                    continue
                logger.error("L'IA n'a pas produit de contenu après %d tentatives", MAX_RETRIES)
                return None

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
            logger.error(
                "Erreur %s (tentative %d/%d) : %s",
                provider_name, attempt, MAX_RETRIES, exc,
            )
            if _is_rate_limited(exc) and attempt < MAX_RETRIES:
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 5s, 10s, 20s, 40s, 80s
                logger.warning(
                    "Rate limit %s détecté — nouvelle tentative dans %ds",
                    provider_name, wait,
                )
                time.sleep(wait)
                continue
            return None

    return None


def generate_tweet(title: str, url: str, source: str, summary: str = "") -> Optional[str]:
    """
    Génère un tweet en français à partir d'un article.

    Stratégie multi-fournisseurs :
      1. Gemini (principal, gratuit, fiable)
      2. Groq (fallback, si Gemini est indisponible ou rate-limité)

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

    # ── 1. Fournisseur principal : Gemini ──
    gemini_client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    tweet = _generate_with_client(
        client=gemini_client,
        model=config.LLM_MODEL,
        provider_name="Gemini",
        prompt=prompt,
        title=title,
        url=url,
    )
    if tweet:
        return tweet

    # ── 2. Fallback : Groq ──
    if config.GROQ_API_KEY:
        logger.warning("Gemini indisponible — bascule sur Groq (fallback)")
        groq_client = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
        tweet = _generate_with_client(
            client=groq_client,
            model=config.GROQ_MODEL,
            provider_name="Groq",
            prompt=prompt,
            title=title,
            url=url,
        )
        if tweet:
            return tweet
    else:
        logger.warning("GROQ_API_KEY manquante — pas de fallback disponible")

    logger.error("Échec de la génération IA (Gemini + Groq)")
    return None
