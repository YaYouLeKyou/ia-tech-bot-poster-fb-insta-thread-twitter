"""
Configuration centrale de l'agent Twitter — Veille IA & Tech.

Centralise :
  - les clés API (chargées depuis .env)
  - la liste des flux RSS IA & Tech
  - la planification (2 fois par jour)
  - le prompt de génération IA
"""

import os
from dotenv import load_dotenv

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
# Défaut : 08:00, 12:00, 17:00, 20:00 UTC (configurable via .env)
# ─────────────────────────────────────────────────────────────
DEFAULT_SCHEDULE_TIMES = ["08:00", "12:00", "17:00", "20:00"]

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

# ─────────────────────────────────────────────────────────────
# Serveur web (Flask)
# ─────────────────────────────────────────────────────────────
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))

# ─────────────────────────────────────────────────────────────
# Publication
# ─────────────────────────────────────────────────────────────
MAX_TWEET_LENGTH = 230  # < 230 caractères, limite de sécurité
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
# Prompt système pour la génération du tweet
# ─────────────────────────────────────────────────────────────
AI_SYSTEM_PROMPT = (
    "Tu es un journaliste expert en Intelligence Artificielle et en Technologies. "
    "Ton style est informatif, concis et accrocheur. "
    "Tu rédiges des tweets en français destinés à un public passionné de tech."
)

AI_USER_PROMPT_TEMPLATE = (
    "Voici le contenu d'un article de presse technologique :\n"
    "\n"
    "Titre : {title}\n"
    "Source : {source}\n"
    "URL : {url}\n"
    "Résumé : {summary}\n"
    "\n"
    "Rédige un tweet en français respectant STRICTEMENT ces règles :\n"
    "1. Maximum {max_length} caractères (compte incluant les hashtags et le lien).\n"
    "2. Un ton journalistique informatif, avec une accroche percutante.\n"
    "3. Une synthèse claire des points essentiels de l'article.\n"
    "4. Termine par 2 hashtags ciblés et pertinents, par exemple #IA ou #Tech.\n"
    "5. N'utilise que du texte : pas d'emojis, pas de citation du titre exact.\n"
    "6. Le tweet doit se terminer par le lien de l'article : {url}\n"
    "\n"
    "Renvoie UNIQUEMENT le texte du tweet, sans guillemets ni commentaire."
)
