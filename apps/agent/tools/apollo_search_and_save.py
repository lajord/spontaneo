import json
import os
import time

import requests
from langchain_core.tools import tool

from config import RATE_LIMIT_APOLLO, TOOL_MAX_RETRIES, TOOL_RETRY_BASE_DELAY, HTTP_TIMEOUT_APOLLO
from runtime import raise_if_cancelled, get_context_value
from tools.candidate_store import get_candidates_rows, save_candidates_batch


def _get_apollo_key():
    return os.getenv("APOLLO_API_KEY", "")


APOLLO_BASE_URL = "https://api.apollo.io"

_last_call_time = 0.0
RATE_LIMIT_DELAY = RATE_LIMIT_APOLLO
_MAX_RETRIES = TOOL_MAX_RETRIES
_BASE_DELAY = TOOL_RETRY_BASE_DELAY


def _rate_limit():
    """Attend si necessaire pour respecter le rate limit Apollo."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_call_time = time.time()


def _current_total() -> int:
    return len(get_candidates_rows())


def _preview_companies(companies: list[dict], max_items: int = 3) -> str:
    preview = []
    for company in companies[:max_items]:
        name = company.get("name", "").strip()
        website = company.get("websiteUrl", "").strip()
        if name and website:
            preview.append(f"{name} -> {website}")
        elif name:
            preview.append(name)
    return " | ".join(preview)


def _format_report(found_count: int, save_result: dict, companies: list[dict] | None = None) -> str:
    if not save_result.get("ok"):
        return (
            f"apollo_search_and_save: {found_count} entreprises trouvees, mais sauvegarde echouee. "
            f"{save_result.get('error', 'Erreur inconnue.')}"
        )

    rejected = save_result.get("rejected", 0)
    reject_note = f", rejected: {rejected}" if rejected else ""
    preview = _preview_companies(companies or [])
    report = (
        f"apollo_search_and_save: added: {save_result.get('added', 0)} "
        f"(found: {found_count}, total: {save_result.get('total', 0)}, "
        f"duplicates: {save_result.get('duplicates', 0)}{reject_note})."
    )
    if preview:
        report += f"\nsource_preview: {preview}"
    return report


@tool
def apollo_search_and_save(
    locations: list[str] = None,
    keywords: list[str] = None,
    job_titles: list[str] = None,
    employee_ranges: list[str] = None,
    organization_name: str = None,
    page: int = 1,
    per_page: int = 25,
) -> str:
    """Recherche des entreprises dans Apollo.io ET les sauvegarde immediatement.

    Utilise ce tool pour DECOUVRIR des entreprises puis les enregistrer
    directement en base de donnees, sans appel separe a `save_candidates`.

    IMPORTANT :
    - ce tool remplace la sequence `apollo_search` -> `save_candidates` ;
    - il faut lire son compte-rendu pour connaitre `added` et `total` ;
    - `total` correspond au total actuel en base de donnees.

    REGLE APOLLO :
    - NE JAMAIS combiner `keywords` et `job_titles` dans un seul appel ;
    - fais DEUX appels separes si tu veux tester les deux angles.

    Args:
        locations: Localisations, ex: ["Paris, France", "Lyon, France"]
        keywords: Tags secteur/activite.
        job_titles: Titres de poste recherches.
        employee_ranges: Tailles d'entreprise.
        organization_name: Recherche par nom d'entreprise.
        page: Numero de page (commence a 1, max 5 pages).
        per_page: Resultats par page (max 100).

    Returns:
        Texte court de la forme :
        `apollo_search_and_save: added: X (found: Y, total: Z, duplicates: D).`
    """
    raise_if_cancelled()

    ctx_target = get_context_value("target_count")
    if isinstance(ctx_target, int) and ctx_target > 0:
        per_page = min(per_page, ctx_target)

    if keywords and job_titles:
        return (
            "apollo_search_and_save: INTERDIT de combiner keywords et job_titles dans un seul appel. "
            f"added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
        )

    api_key = _get_apollo_key()
    if not api_key:
        return (
            "apollo_search_and_save: APOLLO_API_KEY non configuree dans le .env. "
            f"added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
        )

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

    url = f"{APOLLO_BASE_URL}/api/v1/organizations/search"
    print(f"  [APOLLO] POST {url}")
    print(f"  [APOLLO] Payload: {json.dumps(payload, ensure_ascii=False)}")

    for attempt in range(_MAX_RETRIES):
        try:
            raise_if_cancelled()
            _rate_limit()
            response = requests.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT_APOLLO)

            print(f"  [APOLLO] Status: {response.status_code}")

            if response.status_code == 429:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [APOLLO] Rate limit 429 - retry dans {wait}s (tentative {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                print(f"  [APOLLO ERROR] Response: {response.text[:500]}")
                response.raise_for_status()

            data = response.json()
            organizations = data.get("organizations", [])

            companies = []
            for org in organizations:
                companies.append({
                    "name": org.get("name", ""),
                    "websiteUrl": org.get("website_url", ""),
                    "city": org.get("city", ""),
                    "industry": org.get("industry", ""),
                    "employee_count": org.get("estimated_num_employees"),
                    "description": (org.get("short_description") or "")[:200],
                    "source": "apollo",
                })

            print(f"  [APOLLO] {len(companies)} entreprises trouvees")
            save_result = save_candidates_batch(companies)
            return _format_report(len(companies), save_result, companies)

        except requests.exceptions.Timeout:
            msg = "Timeout Apollo API. Reessaie."
            print(f"  [APOLLO ERROR] {msg}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BASE_DELAY)
                continue
            return f"apollo_search_and_save: {msg} added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
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
            return f"apollo_search_and_save: {msg}"
        except Exception as e:
            msg = f"Erreur Apollo: {type(e).__name__}: {e}"
            print(f"  [APOLLO ERROR] {msg}")
            return f"apollo_search_and_save: {msg}"

    return f"apollo_search_and_save: Echec apres {_MAX_RETRIES} tentatives."
