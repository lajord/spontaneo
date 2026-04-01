import json
import os
import neverbounce_sdk
from langchain_core.tools import tool


def _get_neverbounce_key():
    return os.getenv("NEVER_BOUNCE_API", "")


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
            "message": "NEVER_BOUNCE_API non configuree. Verification impossible.",
        })

    print(f"  [NEVERBOUNCE] Verification: {email}")

    try:
        client = neverbounce_sdk.client(api_key=api_key)
        verification = client.single_check(
            email=email,
            address_info=True,
            credits_info=True,
            timeout=10,
        )

        result = verification.get("result", "unknown")
        print(f"  [NEVERBOUNCE] {email} → {result}")
        return json.dumps({
            "email": email,
            "result": result,
        })

    except Exception as e:
        print(f"  [NEVERBOUNCE ERROR] {type(e).__name__}: {e}")
        return json.dumps({
            "email": email,
            "result": "unknown",
            "message": f"Erreur: {type(e).__name__}: {e}",
        })
