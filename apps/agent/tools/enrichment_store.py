import json
import os
import requests
from langchain_core.tools import tool

from runtime import get_run_context, raise_if_cancelled

_WEB_URL = os.getenv("WEB_URL", "http://web:3000")
_API_ENDPOINT = f"{_WEB_URL}/api/agent/contacts"

# Legacy path garde pour compatibilite debug
OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICHED_CSV = os.path.join(OUTPUT_DIR, "enriched.csv")


def _normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://www.", "http://www.", "https://", "http://"]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


def _ctx() -> dict:
    return get_run_context()


def get_enriched_rows() -> list[dict]:
    ctx = _ctx()
    user_id = ctx.get("user_id")
    job_id = ctx.get("job_id")
    if not user_id or not job_id:
        return []

    try:
        resp = requests.get(
            _API_ENDPOINT,
            params={"userId": user_id, "jobId": job_id},
            timeout=10,
        )
        resp.raise_for_status()
        contacts = resp.json().get("contacts", [])
        return [
            {
                "company_name": c.get("agentCandidate", {}).get("name", ""),
                "company_domain": c.get("agentCandidate", {}).get("domain", ""),
                "company_url": c.get("agentCandidate", {}).get("websiteUrl", ""),
                "contact_name": c.get("name", ""),
                "contact_first_name": c.get("firstName", ""),
                "contact_last_name": c.get("lastName", ""),
                "contact_email": c.get("email", ""),
                "contact_title": c.get("title", ""),
                "contact_phone": c.get("phone", ""),
                "contact_linkedin": c.get("linkedin", ""),
                "email_status": c.get("emailStatus", ""),
                "source": c.get("source", ""),
            }
            for c in contacts
        ]
    except Exception:
        return []


def _save_to_db(contacts: list[dict], company_domain: str) -> str | None:
    ctx = _ctx()
    user_id = ctx.get("user_id")
    job_id = ctx.get("job_id")
    if not user_id or not job_id:
        return None

    api_contacts = []
    for c in contacts:
        api_contacts.append({
            "name": c.get("contact_name", ""),
            "firstName": c.get("contact_first_name", ""),
            "lastName": c.get("contact_last_name", ""),
            "email": c.get("contact_email", ""),
            "title": c.get("contact_title", ""),
            "phone": c.get("contact_phone", ""),
            "linkedin": c.get("contact_linkedin", ""),
            "emailStatus": c.get("email_status", ""),
            "source": c.get("source", ""),
        })

    payload = {
        "userId": user_id,
        "jobId": job_id,
        "companyDomain": company_domain,
        "contacts": api_contacts,
    }

    try:
        resp = requests.post(_API_ENDPOINT, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return f"DB: {data.get('added', 0)} contacts sauvegardes (candidateId: {data.get('agentCandidateId', '?')})"
    except Exception as e:
        return f"DB: Erreur sauvegarde — {type(e).__name__}: {e}"


@tool
def save_enrichment(contacts_json: str) -> str:
    """Sauvegarde les contacts enrichis en base de donnees."""
    raise_if_cancelled()

    try:
        contacts = json.loads(contacts_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide — {e}"

    if not isinstance(contacts, list) or not contacts:
        return "Erreur: Le JSON doit contenir une liste non-vide de contacts."

    normalized_contacts = []
    for contact in contacts:
        normalized_contacts.append({
            "company_name": contact.get("company_name", ""),
            "company_domain": contact.get("company_domain", ""),
            "company_url": contact.get("company_url", ""),
            "contact_name": contact.get("contact_name", ""),
            "contact_first_name": contact.get("contact_first_name", ""),
            "contact_last_name": contact.get("contact_last_name", ""),
            "contact_email": contact.get("contact_email", ""),
            "contact_title": contact.get("contact_title", ""),
            "contact_phone": contact.get("contact_phone", ""),
            "contact_linkedin": contact.get("contact_linkedin", ""),
            "email_status": contact.get("email_status", ""),
            "source": contact.get("source", ""),
        })

    company_domain = ""
    for c in normalized_contacts:
        domain = c.get("company_domain", "") or _normalize_domain(c.get("company_url", ""))
        if domain:
            company_domain = domain
            break

    return _save_to_db(normalized_contacts, company_domain) or "Aucun contact sauvegarde."


@tool
def read_enrichment_summary() -> str:
    """Retourne un resume de l'etat actuel des contacts enrichis."""
    raise_if_cancelled()

    rows = get_enriched_rows()
    total = len(rows)
    by_company = {}
    for row in rows:
        company = row.get("company_name", "Inconnu")
        by_company[company] = by_company.get(company, 0) + 1

    return json.dumps({
        "total": total,
        "by_company": by_company,
        "message": f"{total} contacts enrichis pour {len(by_company)} entreprises.",
    }, ensure_ascii=False)
