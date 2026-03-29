import json
import os
import requests
from langchain_core.tools import tool

from config import HTTP_TIMEOUT_NEVERBOUNCE


NB_BASE_URL = "https://api.neverbounce.com/v4"


def _get_neverbounce_key():
    return os.getenv("NEVERBOUNCE_API_KEY", "")


@tool
def neverbounce_verify(email: str) -> str:
    """Verifie la delivrabilite d'un email via NeverBounce.

    Utilise cet outil APRES avoir trouve un email (via crawl, Perplexity ou Apollo)
    pour verifier qu'il est valide avant de l'enregistrer.

    Resultats possibles :
    - "valid" : l'email existe et peut recevoir des messages
    - "invalid" : l'email n'existe pas ou ne peut pas recevoir
    - "catchall" : le domaine accepte tout (impossible de confirmer individuellement)
    - "disposable" : email jetable (type Mailinator)
    - "unknown" : impossible de determiner (timeout, erreur, ou cle API manquante)

    CONSEIL : ne verifie que les emails qui semblent reels (pas les generiques
    comme info@, contact@, accueil@ — ceux-la sont probablement valides mais inutiles).

    Args:
        email: L'adresse email a verifier (ex: "j.dupont@cabinet-x.fr")

    Returns:
        JSON avec le resultat de la verification.
    """
    if not email or not email.strip():
        return json.dumps({"email": "", "result": "unknown", "message": "Email vide."})

    email = email.strip().lower()

    api_key = _get_neverbounce_key()
    if not api_key:
        return json.dumps({
            "email": email,
            "result": "unknown",
            "message": "NEVERBOUNCE_API_KEY non configuree. Verification impossible.",
        })

    print(f"  [NEVERBOUNCE] Verification: {email}")

    try:
        response = requests.get(
            f"{NB_BASE_URL}/single/check",
            params={"key": api_key, "email": email, "timeout": HTTP_TIMEOUT_NEVERBOUNCE - 5},
            timeout=HTTP_TIMEOUT_NEVERBOUNCE,
        )

        if not response.ok:
            print(f"  [NEVERBOUNCE ERROR] HTTP {response.status_code}")
            return json.dumps({
                "email": email,
                "result": "unknown",
                "message": f"Erreur HTTP {response.status_code}",
            })

        data = response.json()

        if data.get("status") == "success":
            result = data.get("result", "unknown")
            print(f"  [NEVERBOUNCE] {email} → {result}")
            return json.dumps({
                "email": email,
                "result": result,
            })

        print(f"  [NEVERBOUNCE] Status non-success: {data.get('status')}")
        return json.dumps({
            "email": email,
            "result": "unknown",
            "message": f"NeverBounce status: {data.get('status')}",
        })

    except requests.exceptions.Timeout:
        print(f"  [NEVERBOUNCE] Timeout pour {email}")
        return json.dumps({
            "email": email,
            "result": "unknown",
            "message": "Timeout NeverBounce (35s)",
        })
    except Exception as e:
        print(f"  [NEVERBOUNCE ERROR] {type(e).__name__}: {e}")
        return json.dumps({
            "email": email,
            "result": "unknown",
            "message": f"Erreur: {type(e).__name__}: {e}",
        })
