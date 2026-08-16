"""
Script de diagnostic et test de la publication Facebook.

Usage :
    python test_facebook.py

Ce script :
  1. Vérifie la validité du token (debug_token)
  2. Récupère l'ID de page associé au token (/me)
  3. Compare avec le FACEBOOK_PAGE_ID configuré
  4. Tente une publication de test sur la page avec logs détaillés
"""

import logging
import sys

import requests

import config
import facebook_client

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("test-facebook")

GRAPH_API_URL = "https://graph.facebook.com/v19.0"


def check_config() -> None:
    """Vérifie la présence des variables de configuration."""
    print("\n" + "=" * 60)
    print("1 CONFIGURATION")
    print("=" * 60)
    print(f"FB_PAGE_ACCESS_TOKEN   : {'[OK] défini (' + config.FB_PAGE_ACCESS_TOKEN[:25] + '...)' if config.FB_PAGE_ACCESS_TOKEN else '[ERROR] MANQUANT'}")
    print(f"FACEBOOK_PAGE_ID    : {config.FACEBOOK_PAGE_ID or '[ERROR] MANQUANT'}")
    print(f"DRY_RUN             : {config.DRY_RUN}")


def test_token_validity() -> dict:
    """Vérifie la validité du token via debug_token."""
    print("\n" + "=" * 60)
    print("2 VALIDITE DU TOKEN (/debug_token)")
    print("=" * 60)

    facebook = facebook_client.FacebookClient()
    token_info = facebook.check_token()

    if not token_info:
        print("FAIL Impossible de vérifier le token (erreur réseau)")
        return {}

    print(f"is_valid      : {token_info.get('is_valid')}")
    print(f"type          : {token_info.get('type')}")
    print(f"scopes        : {token_info.get('scopes')}")
    print(f"permissions manquantes : {token_info.get('missing_scopes') or 'aucune'}")
    if token_info.get("expires_at"):
        import datetime
        exp = datetime.datetime.fromtimestamp(token_info["expires_at"])
        print(f"expiration    : {exp.strftime('%d/%m/%Y %H:%M')}")
    print(f"user_id       : {token_info.get('user_id')}")
    return token_info


def test_page_matching() -> None:
    """Vérifie que le FACEBOOK_PAGE_ID correspond à la page du token."""
    print("\n" + "=" * 60)
    print("3 CORRESPONDANCE TOKEN PAGE")
    print("=" * 60)

    # Récupère l'ID associé au token via /me
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/me",
            params={"access_token": config.FB_PAGE_ACCESS_TOKEN},
            timeout=30,
        )
        data = response.json()
        print(f"GET /me -> {response.status_code} : {data}")

        if response.status_code == 200:
            token_entity_id = str(data.get("id"))
            token_entity_name = data.get("name", "?")

            configured_page_id = str(config.FACEBOOK_PAGE_ID)

            if token_entity_id == configured_page_id:
                print(f"Token belongs to configured page : {token_entity_name} (ID {token_entity_id})")
            else:
                print(f"MISMATCH !")
                print(f"   - Token page (/me)    : {token_entity_name} (ID {token_entity_id})")
                print(f"   - Configured page (.env) : ID {configured_page_id}")
                print(f"   -> Correct FACEBOOK_PAGE_ID in .env with {token_entity_id}")

        else:
            error = data.get("error", {})
            print(f"Error /me : {error.get('code')} — {error.get('message')}")

    except Exception as exc:
        print(f"Exception : {exc}")


def test_page_info() -> None:
    """Récupère les infos de la page configurée."""
    print("\n" + "=" * 60)
    print("4 INFOS DE LA PAGE CONFIGUREE")
    print("=" * 60)

    try:
        response = requests.get(
            f"{GRAPH_API_URL}/{config.FACEBOOK_PAGE_ID}",
            params={
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
                "fields": "id,name,about,fan_count,link",
            },
            timeout=30,
        )
        data = response.json()
        print(f"GET /{config.FACEBOOK_PAGE_ID} -> {response.status_code}")

        if response.status_code == 200:
            print(f"Name    : {data.get('name')}")
            print(f"ID     : {data.get('id')}")
            print(f"Fans   : {data.get('fan_count')}")
            print(f"Link   : {data.get('link')}")
            print("Page is accessible with token")
        else:
            error = data.get("error", {})
            print(f"Error : {error.get('code')} — {error.get('message')}")
            print("   -> Token has no access to this page !")
            print("   -> Verify FACEBOOK_PAGE_ID is the ID of the page managed by this token.")

    except Exception as exc:
        print(f"Exception : {exc}")


def test_instagram_account() -> None:
    """Vérifie si un compte Instagram est associé à la page Facebook."""
    print("\n" + "=" * 60)
    print("5 COMPTE INSTAGRAM ASSOCIE")
    print("=" * 60)

    if not config.INSTAGRAM_ACCOUNT_ID:
        print("INSTAGRAM_ACCOUNT_ID : FAIL non configuré dans .env")
    else:
        print(f"INSTAGRAM_ACCOUNT_ID : {config.INSTAGRAM_ACCOUNT_ID}")

    # Essaie de récupérer le compte Instagram associé à la page
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/{config.FACEBOOK_PAGE_ID}",
            params={
                "access_token": config.FB_PAGE_ACCESS_TOKEN,
                "fields": "id,name,instagram_business_account",
            },
            timeout=30,
        )
        data = response.json()
        print(f"GET /{config.FACEBOOK_PAGE_ID}?fields=instagram_business_account -> {response.status_code}")

        if response.status_code == 200:
            ig_account = data.get("instagram_business_account")
            if ig_account:
                print(f"Instagram account associated : ID={ig_account.get('id')} username={ig_account.get('username')}")
                if not config.INSTAGRAM_ACCOUNT_ID:
                    print(f"   -> Add INSTAGRAM_ACCOUNT_ID={ig_account.get('id')} in .env")
            else:
                print("FAIL No Instagram account associated to this Facebook page")
                print("   -> Connect an Instagram account to the page in Meta Business Suite")
        else:
            error = data.get("error", {})
            print(f"Error : {error.get('code')} — {error.get('message')}")

    except Exception as exc:
        print(f"Exception : {exc}")


def test_post() -> None:
    """Tente une publication de test."""
    print("\n" + "=" * 60)
    print("6 PUBLICATION DE TEST FACEBOOK")
    print("=" * 60)

    facebook = facebook_client.FacebookClient()
    if not facebook.configure():
        print("FAIL Configuration Facebook échouée")
        return

    test_message = "Test de publication depuis l'interface de veille — ceci est un test technique."
    print(f"Test message : {test_message}")
    print(f"Post URL : {GRAPH_API_URL}/{config.FACEBOOK_PAGE_ID}/feed")

    # Publication réelle
    success = facebook.post_to_page(message=test_message)
    if success:
        print("SUCCESS Test post SUCCESS !")
    else:
        print("FAILED Test post FAILED (see logs above)")


def test_post_instagram() -> None:
    """Tente une publication de test sur Instagram."""
    print("\n" + "=" * 60)
    print("7 PUBLICATION DE TEST INSTAGRAM")
    print("=" * 60)

    if not config.INSTAGRAM_ACCOUNT_ID:
        print("FAIL INSTAGRAM_ACCOUNT_ID non configuré — impossible de tester Instagram")
        return

    facebook = facebook_client.FacebookClient()
    if not facebook.configure():
        print("FAIL Configuration Facebook échouée")
        return

    test_message = "Test de publication Instagram depuis l'interface de veille."
    print(f"Test message : {test_message}")
    print(f"Instagram Account ID : {config.INSTAGRAM_ACCOUNT_ID}")

    # Publication réelle
    success = facebook.post_to_instagram(message=test_message)
    if success:
        print("SUCCESS Instagram test post SUCCESS !")
    else:
        print("FAILED Instagram test post FAILED (see logs above)")


def main() -> None:
    """Point d'entrée principal du test."""
    print("Facebook Diagnostic - Starting")
    check_config()
    if not config.FB_PAGE_ACCESS_TOKEN:
        print("\nFAIL FB_PAGE_ACCESS_TOKEN manquant — impossible de continuer.")
        return

    test_token_validity()
    test_page_matching()
    test_page_info()
    test_instagram_account()
    test_post()
    test_post_instagram()

    print("\n" + "=" * 60)
    print("SUCCESS DIAGNOSTIC COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()