"""
Client Facebook (Meta Graph API) — publication de posts sur une page.

Responsabilités :
  - Authentification via token d'accès Meta (Page Access Token)
  - Publication d'un post texte + lien sur une page Facebook
  - Vérification de la configuration
  - Mode simulation (dry-run) : affiche le post sans le publier
"""

import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

# URL de base de la Graph API Meta
GRAPH_API_URL = "https://graph.facebook.com/v19.0"


class FacebookClient:
    """Client Facebook pour la publication de posts (Graph API)."""

    def __init__(self) -> None:
        self._is_configured = False

    def configure(self) -> bool:
        """
        Vérifie que la configuration Facebook est valide.

        :return: True si la configuration est valide, False sinon
        """
        if not config.META_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
            logger.error(
                "Configuration Facebook incomplète. "
                "Vérifiez META_ACCESS_TOKEN et FACEBOOK_PAGE_ID dans .env"
            )
            return False

        self._is_configured = True
        logger.info("Client Facebook configuré (page ID : %s)", config.FACEBOOK_PAGE_ID)
        return True

    def post_to_page(self, message: str, link: str = "") -> bool:
        """
        Publie un post sur la page Facebook.

        :param message: Contenu du post
        :param link: Lien à joindre au post (optionnel)
        :return: True si publié (ou simulé), False en cas d'échec
        """
        if not message:
            logger.error("Message vide — impossible de publier")
            return False

        # ── Mode simulation (Dry-Run) : affiche sans publier ──
        if config.DRY_RUN:
            print("\n" + "=" * 60)
            print("🧪 MODE TEST (DRY RUN) — POST FACEBOOK NON ENVOYÉ")
            print("=" * 60)
            print(f"Page ID : {config.FACEBOOK_PAGE_ID}")
            print(f"Message : {message}")
            if link:
                print(f"Lien    : {link}")
            print("=" * 60 + "\n")
            logger.info("Dry-run : post Facebook affiché dans la console")
            return True

        if not self._is_configured:
            logger.error("Client Facebook non configuré — appelez configure() d'abord")
            return False

        try:
            # Construction des paramètres de la requête
            params = {
                "access_token": config.META_ACCESS_TOKEN,
                "message": message,
            }
            if link:
                params["link"] = link

            # Publication sur la page
            url = f"{GRAPH_API_URL}/{config.FACEBOOK_PAGE_ID}/feed"
            response = requests.post(url, data=params, timeout=30)
            data = response.json()

            if response.status_code == 200 and data.get("id"):
                post_id = data["id"]
                logger.info("Post Facebook publié avec succès — ID : %s", post_id)
                return True

            logger.error("Erreur Facebook API : %s", data)
            return False

        except requests.RequestException as exc:
            logger.error("Erreur réseau lors de la publication Facebook : %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur inattendue lors de la publication Facebook : %s", exc)
            return False

    def get_page_info(self) -> Optional[dict]:
        """
        Récupère les informations de la page Facebook.

        :return: dict avec les infos de la page, ou None si erreur
        """
        if not self._is_configured:
            logger.error("Client Facebook non configuré — appelez configure() d'abord")
            return None

        try:
            url = f"{GRAPH_API_URL}/{config.FACEBOOK_PAGE_ID}"
            params = {
                "access_token": config.META_ACCESS_TOKEN,
                "fields": "id,name,about,fan_count,link",
            }
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if response.status_code == 200:
                logger.info("Page Facebook récupérée : %s", data.get("name", "inconnue"))
                return data

            logger.error("Erreur Facebook API (get_page_info) : %s", data)
            return None

        except requests.RequestException as exc:
            logger.error("Erreur réseau lors de la récupération de la page : %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur inattendue (get_page_info) : %s", exc)
            return None