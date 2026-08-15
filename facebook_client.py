"""
Client Facebook (Meta Graph API) — publication de posts sur une page.

Responsabilités :
  - Authentification via token d'accès Meta (Page Access Token)
  - Publication d'un post texte + lien sur une page Facebook
  - Vérification de la configuration
  - Vérification de la validité du token (debug)
  - Mode simulation (dry-run) : affiche le post sans le publier
"""

import logging
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

# URL de base de la Graph API Meta
GRAPH_API_URL = "https://graph.facebook.com/v19.0"
DEBUG_TOKEN_URL = "https://graph.facebook.com/v19.0/debug_token"

# Cache de validation token — évite des appels réseau répétés à /debug_token
# lors d'un même cycle de publication (Facebook + Instagram).
# TTL courte (120 s) : un token expiré reste dans le cache sans requête inutile
# jusqu'au prochain cycle.
_token_validation_cache: dict = {}
_TOKEN_CACHE_TTL = 120  # secondes


class FacebookClient:
    """Client Facebook pour la publication de posts (Graph API)."""

    def __init__(self) -> None:
        self._is_configured = False

    def configure(self, verify_token: Optional[bool] = None) -> bool:
        """
        Vérifie que la configuration Facebook est valide.

        :param verify_token: Si True, vérifie aussi la validité du token
                              auprès de l'API Meta (requête réseau).
                              Si None (défaut), active la vérification en mode
                              réel et la désactive en mode DRY_RUN.
        :return: True si la configuration est valide, False sinon
        """
        if verify_token is None:
            verify_token = not config.DRY_RUN

        if not config.FB_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
            logger.error(
                "Configuration Facebook incomplète. "
                "Vérifiez FB_PAGE_ACCESS_TOKEN et FACEBOOK_PAGE_ID dans .env"
            )
            return False

        if verify_token:
            token_info = self.check_token()
            if not token_info or not token_info.get("is_valid"):
                if token_info and not token_info.get("is_valid"):
                    logger.error(
                        "Token Meta expiré ou invalide — publication Facebook/Instagram "
                        "désactivée. Générez un nouveau Page Access Token sur "
                        "https://developers.facebook.com/tools/access-token/ "
                        "avec les permissions pages_read_engagement et pages_manage_posts, "
                        "puis redémarrez l'application."
                    )
                return False

        self._is_configured = True
        logger.info("Client Facebook configuré (page ID : %s)", config.FACEBOOK_PAGE_ID)
        return True

    def check_token(self) -> Optional[dict]:
        """
        Vérifie la validité du token d'accès à l'aide de l'API /debug_token.

        Utilise un cache en mémoire (TTL 120 s) pour éviter des appels
        réseau répétés lors d'un même cycle de publication.

        :return: dict d'informations sur le token (is_valid, expires_at,
                 scopes, type) ou None en cas d'erreur réseau.
        """
        if not config.FB_PAGE_ACCESS_TOKEN:
            logger.error("FB_PAGE_ACCESS_TOKEN manquant — impossible de vérifier le token")
            return None

        # Vérification du cache
        cached = _token_validation_cache.get("result")
        cached_at = _token_validation_cache.get("checked_at", 0)
        if cached is not None and (time.time() - cached_at < _TOKEN_CACHE_TTL):
            return cached

        try:
            response = requests.get(
                DEBUG_TOKEN_URL,
                params={
                    "input_token": config.FB_PAGE_ACCESS_TOKEN,
                    "access_token": config.FB_PAGE_ACCESS_TOKEN,
                },
                timeout=30,
            )
            data = response.json()

            if response.status_code != 200:
                error = data.get("error", {})
                logger.error(
                    "Erreur de vérification du token Meta : %s — %s",
                    error.get("code"),
                    error.get("message"),
                )
                return {
                    "is_valid": False,
                    "error_code": error.get("code"),
                    "error_message": error.get("message", ""),
                }

            token_data = data.get("data", {})
            is_valid = token_data.get("is_valid", False)
            scopes = token_data.get("scopes", [])
            expires_at = token_data.get("expires_at")

            # Vérifie les permissions essentielles pour publier sur une page
            required_scopes = ["pages_read_engagement", "pages_manage_posts"]
            missing_scopes = [s for s in required_scopes if s not in scopes]

            result = {
                "is_valid": is_valid,
                "scopes": scopes,
                "missing_scopes": missing_scopes,
                "expires_at": expires_at,
                "type": token_data.get("type", ""),
                "app_id": token_data.get("app_id"),
                "user_id": token_data.get("user_id"),
            }

            if not is_valid:
                logger.error(
                    "Token Meta INVALIDE (code 190 subcode 467) — "
                    "la session a été révoquée ou le token a expiré. "
                    "Générez un nouveau token sur https://developers.facebook.com/tools/access-token/"
                )
            elif missing_scopes:
                logger.warning(
                    "Token Meta valide mais permissions manquantes : %s. "
                    "Requis : pages_read_engagement, pages_manage_posts",
                    missing_scopes,
                )
            else:
                logger.info("Token Meta valide — scopes : %s", scopes)

            _token_validation_cache["result"] = result
            _token_validation_cache["checked_at"] = time.time()
            return result

        except requests.RequestException as exc:
            logger.error("Erreur réseau lors de la vérification du token Meta : %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur inattendue lors de la vérification du token Meta : %s", exc)
            return None

    def reset_token_cache(self) -> None:
        """Force un re-check du token au prochain appel à check_token()."""
        _token_validation_cache.clear()
        logger.info("Cache de validation token vidé — prochain appel check_token() refera le token")

    def _post_with_retry(self, url: str, data: dict, timeout: int = 30, retries: int = 3) -> requests.Response:
        """
        Effectue un POST avec retry exponentiel pour les erreurs réseau temporaires.

        :return: La réponse requests
        :raises: requests.RequestException si toutes les tentatives échouent
        """
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return requests.post(url, data=data, timeout=timeout)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Tentative POST %d/%d échouée (%s) — nouvelle tentative dans %ds",
                        attempt + 1, retries, exc, wait,
                    )
                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]

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
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
                "message": message,
            }
            if link:
                params["link"] = link

            # Publication sur la page
            url = f"{GRAPH_API_URL}/{config.FACEBOOK_PAGE_ID}/feed"
            logger.debug(
                "Envoi du post Facebook : POST %s | paramètres: %s | message (%d caractères)",
                url,
                {k: ("***" if k == "access_token" else v) for k, v in params.items()},
                len(message),
            )
            response = self._post_with_retry(url, params)
            data = response.json()

            logger.debug(
                "Réponse Facebook (%d) : %s",
                response.status_code,
                str(data)[:500],
            )

            if response.status_code == 200 and data.get("id"):
                post_id = data["id"]
                logger.info("Post Facebook publié avec succès — ID : %s", post_id)
                return True

            error = data.get("error", {})
            logger.error(
                "Erreur Facebook API (%d) : code=%s type=%s message=%s | page_id=%s | token_type=%s",
                response.status_code,
                error.get("code"),
                error.get("type"),
                error.get("message"),
                config.FACEBOOK_PAGE_ID,
                self._token_type if hasattr(self, "_token_type") else "inconnu",
            )
            logger.error("  → Réponse complète : %s", data)
            return False

        except requests.RequestException as exc:
            logger.error("Erreur réseau lors de la publication Facebook : %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur inattendue lors de la publication Facebook : %s", exc)
            return False

    def get_token_page_id(self) -> Optional[str]:
        """
        Retourne l'identifiant de la page associée au token.
        Utilise /me (si token page) ou /me/accounts (si token user).

        :return: page_id si trouvé, None sinon
        """
        try:
            # Essaie /me d'abord (fonctionne avec un token de type PAGE)
            response = requests.get(
                f"{GRAPH_API_URL}/me",
                params={"access_token": config.FB_PAGE_ACCESS_TOKEN},
                timeout=30,
            )
            data = response.json()

            if response.status_code == 200 and data.get("id"):
                logger.info("Token associé à la page/entité : %s (%s)", data.get("id"), data.get("name", "?"))
                return str(data.get("id"))

            # Sinon essaie /me/accounts (token utilisateur)
            response = requests.get(
                f"{GRAPH_API_URL}/me/accounts",
                params={"access_token": config.FB_PAGE_ACCESS_TOKEN},
                timeout=30,
            )
            data = response.json()
            if response.status_code == 200:
                pages = data.get("data", [])
                if pages:
                    logger.info("Pages gérées par le token : %s", [(p.get("id"), p.get("name")) for p in pages])
                    return str(pages[0].get("id"))
                logger.warning("Token utilisateur mais aucune page associée dans /me/accounts")

            error = data.get("error", {})
            logger.error("Erreur get_token_page_id : %s", error)
            return None

        except requests.RequestException as exc:
            logger.error("Erreur réseau get_token_page_id : %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur inattendue get_token_page_id : %s", exc)
            return None

    def post_to_instagram(self, message: str) -> bool:
        """
        Publie un post texte sur un compte Instagram associé à la page Facebook.

        Utilise l'API Instagram Content Publishing :
        1. Crée un container média (POST /{ig_user_id}/media avec media_type=TEXT)
        2. Publie le container (POST /{ig_user_id}/media_publish)

        :param message: Contenu du post Instagram
        :return: True si publié (ou simulé), False en cas d'échec
        """
        if not message:
            logger.error("Message vide — impossible de publier sur Instagram")
            return False

        if not config.INSTAGRAM_ACCOUNT_ID:
            logger.error(
                "INSTAGRAM_ACCOUNT_ID manquant — impossible de publier sur Instagram. "
                "Renseignez INSTAGRAM_ACCOUNT_ID dans .env"
            )
            return False

        if not config.FB_PAGE_ACCESS_TOKEN:
            logger.error("FB_PAGE_ACCESS_TOKEN manquant — impossible de publier sur Instagram")
            return False

        # ── Mode simulation (Dry-Run) : affiche sans publier ──
        if config.DRY_RUN:
            print("\n" + "=" * 60)
            print("🧪 MODE TEST (DRY RUN) — POST INSTAGRAM NON ENVOYÉ")
            print("=" * 60)
            print(f"Instagram Account ID : {config.INSTAGRAM_ACCOUNT_ID}")
            print(f"Message : {message}")
            print("=" * 60 + "\n")
            logger.info("Dry-run : post Instagram affiché dans la console")
            return True

        try:
            # 1. Création du container média texte
            create_url = f"{GRAPH_API_URL}/{config.INSTAGRAM_ACCOUNT_ID}/media"
            create_params = {
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
                "media_type": "TEXT",
                "message": message,
            }
            logger.debug(
                "Création du container Instagram : POST %s | media_type=TEXT | message (%d caractères)",
                create_url,
                len(message),
            )

            create_response = self._post_with_retry(create_url, create_params)
            create_data = create_response.json()

            logger.debug("Réponse création container (%d) : %s", create_response.status_code, str(create_data)[:500])

            if create_response.status_code != 200 or not create_data.get("id"):
                error = create_data.get("error", {})
                logger.error(
                    "Erreur création container Instagram (%d) : code=%s message=%s | ig_user_id=%s",
                    create_response.status_code,
                    error.get("code"),
                    error.get("message"),
                    config.INSTAGRAM_ACCOUNT_ID,
                )
                logger.error("  → Réponse complète : %s", create_data)
                return False

            container_id = create_data["id"]
            logger.info("Container Instagram créé — ID : %s", container_id)

            # 2. Publication du container
            publish_url = f"{GRAPH_API_URL}/{config.INSTAGRAM_ACCOUNT_ID}/media_publish"
            publish_params = {
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
                "creation_id": container_id,
            }
            logger.debug("Publication du container Instagram : POST %s", publish_url)

            publish_response = self._post_with_retry(publish_url, publish_params)
            publish_data = publish_response.json()

            logger.debug("Réponse publication container (%d) : %s", publish_response.status_code, str(publish_data)[:500])

            if publish_response.status_code == 200 and publish_data.get("id"):
                media_id = publish_data["id"]
                logger.info("Post Instagram publié avec succès — Media ID : %s", media_id)
                return True

            error = publish_data.get("error", {})
            logger.error(
                "Erreur publication Instagram (%d) : code=%s message=%s | container_id=%s",
                publish_response.status_code,
                error.get("code"),
                error.get("message"),
                container_id,
            )
            logger.error("  → Réponse complète : %s", publish_data)
            return False

        except requests.RequestException as exc:
            logger.error("Erreur réseau lors de la publication Instagram : %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Erreur inattendue lors de la publication Instagram : %s", exc)
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
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
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