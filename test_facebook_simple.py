"""
Test script to post a test message on a Facebook page.

Usage:
    python test_facebook_simple.py

This script tests Facebook page posting functionality by:
  1. Checking configuration (token and page ID)
  2. Posting a test message to the configured Facebook page
"""

import config
import facebook_client


def main():
    print("Facebook Test Post - Starting")
    print("=" * 60)

    # Check configuration
    print("\n1 CONFIGURATION")
    print("=" * 60)
    if not config.FB_PAGE_ACCESS_TOKEN:
        print("FB_PAGE_ACCESS_TOKEN : ERROR MISSING")
        print("\n❌ FB_PAGE_ACCESS_TOKEN manquant — impossible de continuer.")
        return
    else:
        print(f"FB_PAGE_ACCESS_TOKEN   : [OK] défini ({config.FB_PAGE_ACCESS_TOKEN[:25]}...)")

    if not config.FACEBOOK_PAGE_ID:
        print("FACEBOOK_PAGE_ID    : ERROR MISSING")
        return
    else:
        print(f"FACEBOOK_PAGE_ID    : {config.FACEBOOK_PAGE_ID}")

    print(f"DRY_RUN             : {config.DRY_RUN}")

    # Configure Facebook client
    print("\n2 CONFIGURATION FACEBOOK")
    print("=" * 60)
    facebook = facebook_client.FacebookClient()
    if not facebook.configure():
        print("FAIL Configuration Facebook échouée")
        return
    print("Client Facebook configuré")

    # Post test message
    print("\n3 PUBLICATION DE TEST")
    print("=" * 60)

    test_message = "Test de publication depuis l'interface de veille — ceci est un test technique."
    print(f"Message de test : {test_message}")
    print(f"Page ID : {config.FACEBOOK_PAGE_ID}")

    # Post the message
    success = facebook.post_to_page(message=test_message)
    if success:
        print("SUCCESS Publication de test réussie !")
        print("\n" + "=" * 60)
        print("SUCCESS TEST TERMINÉ AVEC SUCCÈS")
        print("=" * 60)
    else:
        print("FAILED Publication de test échouée (voir logs ci-dessus)")
        return


if __name__ == "__main__":
    main()