"""
Configuration centrale de l'agent Twitter — Veille IA & Tech.

Centralise :
  - les clés API (chargées depuis .env)
  - la liste des flux RSS IA & Tech
  - la planification (2 fois par jour)
  - le prompt de génération IA
"""

import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Chargement des variables d'environnement (.env)
load_dotenv()

# ─────────────────────────────────────────────────────────────
# API Twitter (X) — V2
# ─────────────────────────────────────────────────────────────
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# ─────────────────────────────────────────────────────────────
# API LLM (OpenAI SDK compatible — Gemini / Groq)
# ─────────────────────────────────────────────────────────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
# Nombre max de tokens — Gemini a un mode "thinking" qui consomme
# des tokens avant la réponse. 2000 garantit un tweet complet.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

# Fallback Groq (si quota Gemini épuisé)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ─────────────────────────────────────────────────────────────
# Fallback LLM — Groq (si Gemini est indisponible)
# ─────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/compound-mini")

# ─────────────────────────────────────────────────────────────
# API Facebook / Meta (Graph API)
# ─────────────────────────────────────────────────────────────
# Nouveau nom de variable : FB_PAGE_ACCESS_TOKEN
# (avec rétrocompatibilité : META_ACCESS_TOKEN si FB_PAGE_ACCESS_TOKEN absent)
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", os.getenv("META_ACCESS_TOKEN", ""))
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

# ── Renouvellement automatique des tokens ────────────────────
# Identifiants de l'application Facebook (nécessaires pour fb_exchange_token)
# https://developers.facebook.com/apps/ → votre app → Paramètres → Identifiants
FB_APP_ID = os.getenv("FB_APP_ID", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")

# Nombre de jours entre deux renouvellements automatiques des tokens.
# Les tokens Meta/Threads durent 60 jours — un renouvellement tous les
# 30 jours garantit une marge de sécurité confortable.
TOKEN_RENEWAL_DAYS = int(os.getenv("TOKEN_RENEWAL_DAYS", "30"))

# ─────────────────────────────────────────────────────────────
# API Threads (Meta)
# ─────────────────────────────────────────────────────────────
# Token d'accès Threads (lié au compte Instagram/Facebook)
# Généré via https://developers.facebook.com/
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", os.getenv("FB_PAGE_ACCESS_TOKEN", ""))

# ─────────────────────────────────────────────────────────────
# Flux RSS spécialisés « IA & Tech »
# ─────────────────────────────────────────────────────────────
DEFAULT_RSS_FEEDS = [
    # 🇫🇷 Francophone
    "https://www.presse-citron.net/feed/",
    "https://www.clubic.com/feed/news.rss",
    "https://www.01net.com/feed/",
    "https://www.frandroid.com/feed",
    # 🇬🇧 / 🇺🇸 International
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/index.xml",
]

# Liste des flux effectifs :
#   - Si la variable d'environnement RSS_FEED_URLS est définie, on l'utilise
#   - Sinon, on retombe sur la liste par défaut ci-dessus
_env_feeds = os.getenv("RSS_FEED_URLS", "").strip()
if _env_feeds:
    RSS_FEEDS = [url.strip() for url in _env_feeds.split(",") if url.strip()]
else:
    RSS_FEEDS = DEFAULT_RSS_FEEDS

# ─────────────────────────────────────────────────────────────
# Base de données SQLite (anti-doublons)
# ─────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "news_bot.db")

# ─────────────────────────────────────────────────────────────
# Planification — Breaking News par heures fixes
# Défaut : 07:00, 12:00, 17:00, 20:00 heure de PARIS (configurable via .env)
# Les heures saisies dans l'interface / .env sont TOUJOURS en heure de Paris.
# La conversion vers UTC est automatique (gère l'heure d'été/hiver).
# ─────────────────────────────────────────────────────────────
DEFAULT_SCHEDULE_TIMES = ["07:00", "12:00", "17:00", "20:00"]

# Fuseau horaire de publication (heure de Paris)
LOCAL_TIMEZONE = "Europe/Paris"

_env_schedule = os.getenv("SCHEDULE_TIMES", "").strip()
if _env_schedule:
    SCHEDULE_TIMES = [
        t.strip() for t in _env_schedule.split(",") if t.strip()
    ]
else:
    SCHEDULE_TIMES = DEFAULT_SCHEDULE_TIMES

# Fréquence de génération des breaking news (en heures)
# Défaut : 0 = désactivé (utiliser les heures fixes)
NEWS_INTERVAL_HOURS = int(os.getenv("NEWS_INTERVAL_HOURS", "0"))


def paris_time_to_utc(hhmm: str) -> str:
    """
    Convertit une heure de Paris (HH:MM) en heure UTC (HH:MM).
    Gère automatiquement l'heure d'été (UTC+2) et l'heure d'hiver (UTC+1).
    Utilise la date ACTUELLE pour un décalage correct été/hiver.

    :param hhmm: Heure au format HH:MM (heure de Paris)
    :return: Heure UTC correspondante au format HH:MM
    """
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        hour_str, minute_str = hhmm.strip().split(":")
        paris_tz = ZoneInfo(LOCAL_TIMEZONE)
        # Utilise la date du jour pour un calcul correct été/hiver.
        now = datetime.now(paris_tz)
        naive = now.replace(hour=int(hour_str), minute=int(minute_str), second=0, microsecond=0)
        utc_dt = naive.astimezone(timezone.utc)
        return utc_dt.strftime("%H:%M")
    except (ValueError, TypeError, ImportError) as exc:
        # Fallback : retourne l'heure inchangée (considérée déjà UTC)
        logger.warning(
            "Impossible de convertir %s Paris → UTC (%s). Heure utilisée telle quelle.",
            hhmm, exc,
        )
        return hhmm


def utc_time_to_paris(hhmm: str) -> str:
    """
    Convertit une heure UTC (HH:MM) en heure de Paris (HH:MM).
    Gère automatiquement l'heure d'été (UTC+2) et l'heure d'hiver (UTC+1).
    Utilise la date ACTUELLE pour un décalage correct été/hiver.

    :param hhmm: Heure au format HH:MM (UTC)
    :return: Heure de Paris correspondante au format HH:MM
    """
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        hour_str, minute_str = hhmm.strip().split(":")
        paris_tz = ZoneInfo(LOCAL_TIMEZONE)
        # Utilise la date du jour pour un calcul correct été/hiver.
        now_utc = datetime.now(timezone.utc)
        naive_utc = now_utc.replace(hour=int(hour_str), minute=int(minute_str), second=0, microsecond=0)
        paris_dt = naive_utc.astimezone(paris_tz)
        return paris_dt.strftime("%H:%M")
    except (ValueError, TypeError, ImportError) as exc:
        logger.warning(
            "Impossible de convertir %s UTC → Paris (%s). Heure utilisée telle quelle.",
            hhmm, exc,
        )
        return hhmm

# ─────────────────────────────────────────────────────────────
# Serveur web (Flask)
# ─────────────────────────────────────────────────────────────
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))

# ─────────────────────────────────────────────────────────────
# Publication
# ─────────────────────────────────────────────────────────────
MAX_TWEET_LENGTH = 230  # < 230 caractères, limite de sécurité Twitter
MAX_LONG_POST_LENGTH = 2200  # limite Facebook/Instagram
MAX_ARTICLES_TO_PROCESS = 30  # articles maximum scannés par exécution

# ─────────────────────────────────────────────────────────────
# Génération IA — espacement des appels API
# ─────────────────────────────────────────────────────────────
# Délai (en secondes) entre deux appels à l'API LLM lors de la
# génération de plusieurs propositions (anti rate-limit TPM).
# Il est configurable via la variable d'environnement AI_GENERATION_DELAY.
AI_GENERATION_DELAY = int(os.getenv("AI_GENERATION_DELAY", "15"))

# ─────────────────────────────────────────────────────────────
# Historique des breaking news
# ─────────────────────────────────────────────────────────────
# Nombre maximum d'articles conservés dans l'historique.
# Au-delà, les plus anciens sont automatiquement supprimés.
MAX_HISTORY_SIZE = int(os.getenv("MAX_HISTORY_SIZE", "50"))

# ─────────────────────────────────────────────────────────────
# Mode test
# ─────────────────────────────────────────────────────────────
TEST_ON_STARTUP = os.getenv("TEST_ON_STARTUP", "false").strip().lower() == "true"

# ─────────────────────────────────────────────────────────────
# Mode simulation (Dry-Run)
# ─────────────────────────────────────────────────────────────
# true  = affiche le tweet dans la console, ne publie PAS sur Twitter
# false = publie réellement sur Twitter (comportement normal)
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() in ("true", "1", "yes")

# ─────────────────────────────────────────────────────────────
# Notification email — alerte en cas de token expiré
# ─────────────────────────────────────────────────────────────
# Adresse email qui reçoit les alertes de token expiré
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "yanes75@hotmail.fr")

# Activation de l'envoi d'emails (true/false)
SMTP_ENABLED = os.getenv("SMTP_ENABLED", "false").strip().lower() in ("true", "1", "yes")

# Configuration SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_TLS = os.getenv("SMTP_TLS", "true").strip().lower() in ("true", "1", "yes")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)

# ─────────────────────────────────────────────────────────────
# Prompt système pour la génération du tweet
# ─────────────────────────────────────────────────────────────
AI_SYSTEM_PROMPT = (
    "Tu es un journaliste expert en Intelligence Artificielle et en Technologies. "
    "Ton style est informatif, concis et accrocheur. "
    "Tu rédiges UNIQUEMENT des textes en français. "
    "NE UTILISE JAMAIS L'ANGLAIS. "
    "Si le titre ou le résumé de l'article sont en anglais, tu les traduis en français. "
    "Tes tweets sont destinés à un public passionné de tech et d'IA."
)

AI_TITLE_PROMPT_TEMPLATE = (
    "Voici le contenu d'un article de presse technologique :\n"
    "\n"
    "Titre : {title}\n"
    "Source : {source}\n"
    "Résumé : {summary}\n"
    "\n"
    "Rédige un titre COURT en français (OBLIGATOIRE). "
    "NE RÉPONDS PAS EN ANGLAIS. "
    "Si le titre est en anglais, tu le traduis en français. "
    "Maximum 100 caractères. "
    "Renvoie UNIQUEMENT le titre, sans guillemets ni commentaire."
)

AI_USER_PROMPT_TEMPLATE = (
    "Voici le contenu d'un article de presse technologique :\n"
    "\n"
    "Titre : {title}\n"
    "Source : {source}\n"
    "URL : {url}\n"
    "Résumé : {summary}\n"
    "\n"
    "Rédige un tweet 100% en français (OBLIGATOIRE). "
    "NE RÉPONDS PAS EN ANGLAIS. "
    "Si le titre ou le résumé sont en anglais, tu les traduis en français. "
    "Respecte STRICTEMENT ces règles :\n"
    "1. Maximum {max_length} caractères (compte incluant les hashtags et le lien).\n"
    "2. Un ton journalistique informatif, avec une accroche percutante.\n"
    "3. Une synthèse claire des points essentiels de l'article.\n"
    "4. Termine par 2 hashtags ciblés et pertinents, par exemple #IA ou #Tech.\n"
    "5. N'utilise que du texte : pas d'emojis, pas de citation du titre exact.\n"
    "6. Le tweet doit se terminer par le lien de l'article : {url}\n"
    "\n"
    "IMPORTANT : Le tweet doit être 100% en français. "
    "Renvoie UNIQUEMENT le texte du tweet, sans guillemets ni commentaire."
)

AI_LONG_POST_PROMPT_TEMPLATE = (
    "Voici le contenu d'un article de presse technologique :\n"
    "\n"
    "Titre : {title}\n"
    "Source : {source}\n"
    "URL : {url}\n"
    "Résumé : {summary}\n"
    "\n"
    "Rédige un post Facebook/Instagram en français (OBLIGATOIRE). "
    "NE RÉPONDS PAS EN ANGLAIS. "
    "Si le titre ou le résumé sont en anglais, tu les traduis en français. "
    "Respecte STRICTEMENT ces règles :\n"
    "1. Maximum {max_length} caractères (compte incluant les hashtags et le lien).\n"
    "2. Un ton journalistique informatif, avec une accroche percutante.\n"
    "3. Une synthèse détaillée des points essentiels de l'article.\n"
    "4. Termine par 3 hashtags ciblés et pertinents, par exemple #IA #Tech #Innovation.\n"
    "5. N'utilise que du texte : pas d'emojis, pas de citation du titre exact.\n"
    "6. Le post doit se terminer par le lien de l'article : {url}\n"
    "\n"
    "IMPORTANT : Le post doit être 100% en français. "
    "Renvoie UNIQUEMENT le texte du post, sans guillemets ni commentaire."
)
