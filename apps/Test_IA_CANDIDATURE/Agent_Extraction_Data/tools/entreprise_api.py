import json
import time
import requests
from langchain_core.tools import tool

API_ENTREPRISES_URL = "https://recherche-entreprises.api.gouv.fr/search"

# Rate limiting
_last_call_time = 0.0
RATE_LIMIT_DELAY = 0.2

TRANCHES_EFFECTIFS = {
    "00": "0 salarié",
    "01": "1-2 salariés",
    "02": "3-5 salariés",
    "03": "6-9 salariés",
    "11": "10-19 salariés",
    "12": "20-49 salariés",
    "21": "50-99 salariés",
    "22": "100-199 salariés",
    "31": "200-249 salariés",
    "32": "250-499 salariés",
    "41": "500-999 salariés",
    "42": "1000-1999 salariés",
    "51": "2000-4999 salariés",
    "52": "5000-9999 salariés",
    "53": "10000+ salariés",
}


def _rate_limit():
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_call_time = time.time()


@tool
def check_company_size(siren: str) -> str:
    """Vérifie la taille d'une entreprise française via son numéro SIREN.

    Utilise l'API Recherche Entreprises du gouvernement français (gratuite).
    Retourne le nombre de salariés, l'activité, les dirigeants, etc.

    Utilise cet outil quand l'utilisateur a demandé une taille d'entreprise
    spécifique et que tu as trouvé un SIREN sur le site web de l'entreprise
    (via crawl4ai_analyze).

    Args:
        siren: Numéro SIREN de l'entreprise (9 ou 14 chiffres si SIRET)

    Returns:
        JSON avec les infos de l'entreprise : taille, activité, dirigeants, etc.
    """
    # Nettoyer le SIREN (garder que les chiffres, prendre les 9 premiers)
    siren_clean = "".join(c for c in siren if c.isdigit())
    if len(siren_clean) >= 9:
        siren_clean = siren_clean[:9]
    else:
        return json.dumps({"error": f"SIREN invalide: '{siren}' (doit contenir 9 chiffres)"})

    try:
        _rate_limit()
        resp = requests.get(
            API_ENTREPRISES_URL,
            params={"q": siren_clean},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("results"):
            return json.dumps({
                "siren": siren_clean,
                "found": False,
                "error": "Aucune entreprise trouvée pour ce SIREN",
            })

        entreprise = data["results"][0]
        siege = entreprise.get("siege", {})

        # Dirigeants
        dirigeants = []
        for d in entreprise.get("dirigeants", []):
            if d.get("type_dirigeant") == "personne physique":
                dirigeants.append(f"{d.get('prenoms', '')} {d.get('nom', '')}")
            else:
                dirigeants.append(d.get("denomination", "N/A"))

        tranche = entreprise.get("tranche_effectif_salarie") or siege.get("tranche_effectif_salarie", "")
        tranche_label = TRANCHES_EFFECTIFS.get(str(tranche), f"Non renseigné (code: {tranche})")

        result = {
            "found": True,
            "siren": entreprise.get("siren", ""),
            "nom_complet": entreprise.get("nom_complet", ""),
            "activite_principale": entreprise.get("activite_principale", ""),
            "nature_juridique": entreprise.get("nature_juridique", ""),
            "nb_etablissements": entreprise.get("nombre_etablissements", 0),
            "tranche_effectifs": tranche_label,
            "tranche_code": str(tranche),
            "dirigeants": dirigeants,
            "adresse": siege.get("adresse", ""),
            "date_creation": entreprise.get("date_creation", ""),
            "etat_administratif": entreprise.get("etat_administratif", ""),
        }

        print(f"  [API GOV] {result['nom_complet']} → {tranche_label}")
        return json.dumps(result, ensure_ascii=False)

    except requests.exceptions.Timeout:
        return json.dumps({"error": "Timeout API Entreprises"})
    except Exception as e:
        return json.dumps({"error": f"Erreur API Entreprises: {type(e).__name__}: {e}"})
