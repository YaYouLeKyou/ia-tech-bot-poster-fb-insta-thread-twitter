# 🤖 Agent Twitter — Veille IA & Tech

Agent IA autonome qui surveille les actualités **IA & Tech** via des flux RSS, génère un tweet en français optimisé par **DeepSeek/OpenAI**, et le publie automatiquement sur **Twitter/X** — **2 fois par jour**.

## ✨ Fonctionnalités

| Fonctionnalité | Détail |
|---|---|
| 📡 **Veille RSS** | 8 flux IA & Tech (FR + EN) scannés à chaque exécution |
| 🧠 **IA de rédaction** | Tweet en français, ≤ 230 caractères, 2 hashtags ciblés (#IA #Tech) |
| 💾 **Anti-doublons** | Base SQLite locale (`news_bot.db`) — aucun article republié |
| 🐦 **Publication** | API Twitter V2 via `tweepy` (OAuth 1.0a) |
| ⏰ **Planification** | 2 tweets/jour — défaut **08:30 & 17:30 UTC** |
| 🔄 **Déploiement 24/7** | Background Worker Render / Railway (`Procfile` inclus) |

## 📁 Structure du projet

```
agent-twitter/
├── main.py            # Orchestrateur + boucle schedule + logs
├── config.py           # Clés API, flux RSS, planification, prompts
├── database.py         # SQLite anti-doublons (news_bot.db)
├── rss_parser.py       # Extraction RSS via feedparser
├── ai_generator.py     # Génération tweet via DeepSeek/OpenAI
├── twitter_client.py   # Publication Twitter API V2 (tweepy)
├── requirements.txt    # Dépendances Python
├── .env.example        # Modèle de variables d'environnement
├── Procfile            # worker: python main.py (Render/Railway)
├── render.yaml         # Config Blueprint Render (worker)
└── README.md
```

## 🚀 Installation locale

### 1. Prérequis
- Python 3.10+
- Compte développeur Twitter avec accès **API V2** (Read + Write)
- Clé API **DeepSeek** (ou OpenAI)

### 2. Configuration

```bash
# Clonez le projet puis :
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS / Linux

pip install -r requirements.txt
cp .env.example .env
```

Renseignez ensuite le fichier `.env` :

| Variable | Description |
|---|---|
| `TWITTER_API_KEY` | Clé API Twitter (Consumer Key) |
| `TWITTER_API_SECRET` | Secret API Twitter (Consumer Secret) |
| `TWITTER_ACCESS_TOKEN` | Access Token Twitter |
| `TWITTER_ACCESS_SECRET` | Access Token Secret Twitter |
| `TWITTER_BEARER_TOKEN` | Bearer Token Twitter (optionnel) |
| `LLM_API_KEY` | Clé DeepSeek (`sk-…`) ou OpenAI |
| `LLM_BASE_URL` | `https://api.deepseek.com` (DeepSeek) ou `https://api.openai.com/v1` |
| `LLM_MODEL` | `deepseek-chat` (DeepSeek) ou `gpt-4o-mini` (OpenAI) |
| `FB_PAGE_ACCESS_TOKEN` | Page Access Token Meta (permanent, avec permissions `pages_read_engagement`, `pages_manage_posts`) |
| `FACEBOOK_PAGE_ID` | ID de la page Facebook |
| `INSTAGRAM_ACCOUNT_ID` | ID du compte Instagram Business (optionnel) |

### 3. Test rapide

```bash
# Exécute un cycle complet immédiatement (scan + génération + publication)
set TEST_ON_STARTUP=true && python main.py
```

> ⚠️ Avec `TEST_ON_STARTUP=true`, un tweet sera publié **dès le lancement**.
> Mettez-le à `false` pour que le premier tweet parte à l'heure planifiée.

## 🧪 Mode simulation (Dry-Run) — Recommandé pour tester

Le mode **Dry-Run** exécute tout le code (récupération RSS + appel au LLM DeepSeek/GPT)
mais **affiche le tweet dans la console VS Code au lieu de l'envoyer à Twitter**.

### Activation

Dans `.env` :

```env
DRY_RUN=true
```

### Comportement

| Paramètre | Valeur | Effet |
|---|---|---|
| `DRY_RUN=true` | 🧪 Simulation | Le tweet est affiché dans la console, **rien n'est publié** |
| `DRY_RUN=false` | 🐦 Publication réelle | Le tweet est envoyé sur Twitter/X (comportement normal) |

### Exemple de sortie console

```
🧪 MODE TEST (DRY RUN) — TWEET NON ENVOYÉ À TWITTER
🚀 L'IA générative révolutionne la recherche médicale : une
nouvelle étude montre des avancées majeures dans le diagnostic
précoce. #IA #Santé https://example.com/article
```

### Utilisation recommandée

1. **Tant que `DRY_RUN=true`**, lancez le script autant de fois que nécessaire
   pour ajuster les prompts et vérifier la qualité des résumés **sans toucher à Twitter**.
2. **Passez à `DRY_RUN=false`** uniquement quand vous êtes satisfait du résultat.
3. **Combinez avec `TEST_ON_STARTUP=true`** pour tester immédiatement sans attendre
   l'heure planifiée :

```env
DRY_RUN=true
TEST_ON_STARTUP=true
```

```bash
python main.py
```

> ✅ **Avantage** : aucun tweet réel publié, aucun quota API Twitter consommé,
> et vous pouvez itérer sur vos prompts en toute sécurité.

## ⏰ Planification

Le bot tourne **24/7** et publie **2 tweets par jour** :

| Paramètre | Valeur par défaut |
|---|---|
| Heure 1 | **08:30 UTC** |
| Heure 2 | **17:30 UTC** |

Personnalisation dans `.env` :

```env
SCHEDULE_TIMES=08:30,17:30
```

> **Important** : les heures sont en **UTC**. Le script convertit automatiquement
> vers l'heure locale du serveur hébergeur.

## 🌐 Déploiement continu (Render / Railway)

### Option 1 — Render (Background Worker) ✅ Recommandé

Le fichier `render.yaml` configure tout automatiquement via **Blueprint** :

1. Poussez le projet sur **GitHub**
2. Sur [Render](https://render.com) : **New → Blueprint**
3. Sélectionnez votre dépôt — le worker est créé automatiquement
4. Renseignez les variables d'environnement dans le dashboard (les clés marquées `sync: false`)

Variables à renseigner manuellement dans le dashboard Render :
`TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`,
`TWITTER_ACCESS_SECRET`, `TWITTER_BEARER_TOKEN`, `LLM_API_KEY`,
`FB_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID`

### Option 2 — Railway

```bash
# 1. Poussez le projet sur GitHub
# 2. Sur Railway : New Project → Deploy from GitHub
# 3. Configurez un service de type "Worker" :
#    Build Command :  pip install -r requirements.txt
#    Start Command :  python main.py
# 4. Ajoutez les variables d'environnement (mêmes clés que .env)
```

Le `Procfile` (`worker: python main.py`) est reconnu automatiquement
par Railway comme service worker.

### Logs sur le dashboard

Le bot produit des logs clairs et horodatés :

```
2026-08-12 08:30:01 | INFO     | agent-twitter | === Début du cycle de veille ===
2026-08-12 08:30:03 | INFO     | rss_parser    | Total : 24 articles collectés depuis 8 flux
2026-08-12 08:30:03 | INFO     | rss_parser    | 5 nouveaux articles (non encore publiés)
2026-08-12 08:30:05 | INFO     | agent-twitter | Article sélectionné : « … »
2026-08-12 08:30:08 | INFO     | ai_generator  | Tweet généré (198 caractères)
2026-08-12 08:30:10 | INFO     | twitter_client| Tweet publié avec succès — ID : 123456789
```

## 🧠 Flux RSS IA & Tech intégrés

| Source | Flux |
|---|---|
| Presse-Citron 🇫🇷 | `https://www.presse-citron.net/feed/` |
| Clubic 🇫🇷 | `https://www.clubic.com/feed/news.rss` |
| 01Net 🇫🇷 | `https://www.01net.com/feed/` |
| Frandroid 🇫🇷 | `https://www.frandroid.com/feed` |
| TechCrunch AI 🇺🇸 | `https://techcrunch.com/category/artificial-intelligence/feed/` |
| MarkTechPost 🇺🇸 | `https://www.marktechpost.com/feed/` |
| VentureBeat AI 🇺🇸 | `https://venturebeat.com/category/ai/feed/` |
| The Verge 🇺🇸 | `https://www.theverge.com/rss/index.xml` |

Personnalisation dans `.env` :

```env
RSS_FEED_URLS=https://feed1.com/feed/,https://feed2.com/feed/
```

## 🗄️ Base de données anti-doublons

Le fichier `news_bot.db` (SQLite) est créé automatiquement au premier lancement.
Il stocke chaque URL traitée — garantissant **aucune republication** d'une même
actualité, même si le flux re-propose l'article plus tard.

## 📝 Notes techniques

- **Limite tweet** : 230 caractères générés par l'IA (sous la limite 280 de Twitter/X)
- **Anti-échec** : si un article échoue à la génération IA, il est marqué « traité »
  pour ne pas bloquer indéfiniment le worker
- **Troncature intelligente** : si le tweet dépasse 230 caractères, le script
  conserve l'accroche + le lien + les hashtags