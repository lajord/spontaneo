import json
import os
import time
import requests
from langchain_core.tools import tool

from config import RATE_LIMIT_APOLLO, TOOL_MAX_RETRIES, TOOL_RETRY_BASE_DELAY, HTTP_TIMEOUT_APOLLO

def _get_apollo_key():
    return os.getenv("APOLLO_API_KEY", "")
APOLLO_BASE_URL = "https://api.apollo.io"

# Rate limiting
_last_call_time = 0.0
RATE_LIMIT_DELAY = RATE_LIMIT_APOLLO
_MAX_RETRIES = TOOL_MAX_RETRIES
_BASE_DELAY = TOOL_RETRY_BASE_DELAY


def _rate_limit():
    """Attend si nécessaire pour respecter le rate limit Apollo."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_call_time = time.time()


@tool
def apollo_search(
    locations: list[str] = None,
    keywords: list[str] = None,
    job_titles: list[str] = None,
    employee_ranges: list[str] = None,
    organization_name: str = None,
    page: int = 1,
    per_page: int = 100,
) -> str:
    """Recherche des entreprises dans la base Apollo.io (35M+ entreprises).

    Utilise cet outil pour DECOUVRIR des entreprises correspondant aux critères
    de recherche d'emploi. C'est l'outil principal de découverte.

    IMPORTANT — NE JAMAIS combiner keywords et job_titles dans un seul appel.
    Fais DEUX appels séparés :
      - Un appel avec keywords (tags secteur/activité)
      - Un appel avec job_titles (titres de poste)
    Si tu passes les deux en même temps, l'appel sera REJETÉ.

    Args:
        locations: Localisations, ex: ["Paris, France", "Lyon, France"]
        keywords: Tags secteur/activité, ex: ["SaaS", "machine learning"]
        job_titles: Titres de poste recherchés, ex: ["Data Engineer", "Software Engineer"]
        employee_ranges: Tailles d'entreprise, ex: ["11-50", "51-200", "201-500"]
        organization_name: Recherche par nom d'entreprise (optionnel)
        page: Numéro de page pour la pagination (commence à 1, max 5 pages)
        per_page: Résultats par page (max 100)

    Returns:
        JSON avec les entreprises trouvées et infos de pagination.
    """
    dev_mode = os.environ.get("AGENT_DEV_MODE") == "1"
    if dev_mode:
        per_page = min(per_page, 5)

    # Bloquer la combinaison keywords + job_titles
    if keywords and job_titles:
        return json.dumps({
            "error": "INTERDIT de combiner keywords et job_titles dans un seul appel. "
                     "Fais 2 appels séparés : un avec keywords, un avec job_titles.",
            "companies": [],
        })

    api_key = _get_apollo_key()
    if not api_key:
        return json.dumps({
            "error": "APOLLO_API_KEY non configurée dans le .env",
            "companies": [],
        })

    # Construction du body — même format que le ApolloClient existant
    payload = {
        "page": min(page, 5),
        "per_page": min(per_page, 100),
    }

    if locations:
        payload["organization_locations"] = locations
    if keywords:
        payload["q_organization_keyword_tags"] = keywords
    if job_titles:
        payload["q_organization_job_titles"] = job_titles
    if employee_ranges:
        payload["organization_num_employees_ranges"] = employee_ranges
    if organization_name:
        payload["q_organization_name"] = organization_name

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    # Endpoint free plan : /api/v1/organizations/search
    url = f"{APOLLO_BASE_URL}/api/v1/organizations/search"
    print(f"  [APOLLO] POST {url}")
    print(f"  [APOLLO] Payload: {json.dumps(payload, ensure_ascii=False)}")

    for attempt in range(_MAX_RETRIES):
        try:
            _rate_limit()
            response = requests.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT_APOLLO)

            print(f"  [APOLLO] Status: {response.status_code}")

            # Retry sur 429 (rate limit)
            if response.status_code == 429:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [APOLLO] Rate limit 429 — retry dans {wait}s (tentative {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            # Log le body brut en cas d'erreur
            if response.status_code != 200:
                print(f"  [APOLLO ERROR] Response: {response.text[:500]}")
                response.raise_for_status()

            data = response.json()

            organizations = data.get("organizations", [])
            pagination = data.get("pagination", {})

            companies = []
            for org in organizations:
                company = {
                    "name": org.get("name", ""),
                    "website_url": org.get("website_url", ""),
                    "city": org.get("city", ""),
                    "industry": org.get("industry", ""),
                    "employee_count": org.get("estimated_num_employees"),
                    "description": (org.get("short_description") or "")[:200],
                    "source": "apollo",
                }
                companies.append(company)

            print(f"  [APOLLO] {len(companies)} entreprises trouvées (total: {pagination.get('total_entries', '?')})")

            result = {
                "companies": companies,
                "pagination": {
                    "page": pagination.get("page", page),
                    "per_page": pagination.get("per_page", per_page),
                    "total_entries": pagination.get("total_entries", 0),
                    "total_pages": pagination.get("total_pages", 0),
                },
                "count": len(companies),
            }

            return json.dumps(result, ensure_ascii=False)

        except requests.exceptions.Timeout:
            msg = "Timeout Apollo API. Réessaie."
            print(f"  [APOLLO ERROR] {msg}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BASE_DELAY)
                continue
            return json.dumps({"error": msg, "companies": []})
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = ""
            try:
                error_data = e.response.json()
                body = json.dumps(error_data, ensure_ascii=False)
            except Exception:
                body = e.response.text[:500] if e.response is not None else str(e)
            msg = f"Erreur HTTP Apollo {status}: {body}"
            print(f"  [APOLLO ERROR] {msg}")
            return json.dumps({"error": msg, "companies": []})
        except Exception as e:
            msg = f"Erreur Apollo: {type(e).__name__}: {e}"
            print(f"  [APOLLO ERROR] {msg}")
            return json.dumps({"error": msg, "companies": []})

    return json.dumps({"error": "Échec après 3 tentatives", "companies": []})
