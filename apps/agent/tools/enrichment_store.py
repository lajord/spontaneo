import json
import os
import re
import unicodedata

import requests
from langchain_core.tools import tool

from runtime import get_run_context, raise_if_cancelled

_WEB_URL = os.getenv("WEB_URL", "http://web:3000")
_API_ENDPOINT = f"{_WEB_URL}/api/agent/contacts"

_GENERIC_EMAIL_PREFIXES = {
    "contact",
    "info",
    "bonjour",
    "hello",
    "welcome",
    "accueil",
    "cabinet",
    "office",
    "admin",
    "direction",
    "secretariat",
    "secrétariat",
    "rh",
    "recrutement",
    "careers",
    "jobs",
}


def _headers() -> dict[str, str]:
    token = os.getenv("AGENT_INTERNAL_API_TOKEN") or os.getenv("CRON_SECRET")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {"X-Agent-Dev-Internal": "1"}



def _normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://www.", "http://www.", "https://", "http://"]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _city_matches(target_city: str, contact_city: str) -> bool:
    target = _normalize_text(target_city)
    contact = _normalize_text(contact_city)
    if not target:
        return True
    if not contact:
        return False
    if target == contact:
        return True
    target_tokens = set(target.split())
    contact_tokens = set(contact.split())
    return bool(target_tokens) and target_tokens.issubset(contact_tokens)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _is_generic_email(email: str) -> bool:
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        return True
    local_part = normalized.split("@", 1)[0]
    if local_part in _GENERIC_EMAIL_PREFIXES:
        return True
    return False


def _split_contact_name(full_name: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", (full_name or "").strip())
    if not cleaned:
        return "", ""
    parts = cleaned.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


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
            params={"jobId": job_id},
            headers=_headers(),
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
                "contact_specialty": c.get("specialty", ""),
                "contact_phone": c.get("phone", ""),
                "contact_linkedin": c.get("linkedin", ""),
                "email_status": c.get("emailStatus", ""),
                "source": c.get("source", ""),
            }
            for c in contacts
        ]
    except Exception:
        return []


def _save_to_db(
    contacts: list[dict],
    company_domain: str,
    company_url: str = "",
    company_name: str = "",
) -> str | None:
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
            "specialty": c.get("contact_specialty", ""),
            "phone": c.get("contact_phone", ""),
            "linkedin": c.get("contact_linkedin", ""),
            "emailStatus": c.get("email_status", ""),
            "source": c.get("source", ""),
            "qualityScore": c.get("quality_score"),
            "qualityReason": c.get("quality_reason", ""),
            "isDecisionMaker": bool(c.get("is_decision_maker", False)),
        })

    payload = {
        "jobId": job_id,
        "companyDomain": company_domain,
        "companyUrl": company_url,
        "companyName": company_name,
        "contacts": api_contacts,
    }

    try:
        resp = requests.post(_API_ENDPOINT, json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return f"DB: {data.get('added', 0)} contacts sauvegardes (candidateId: {data.get('agentCandidateId', '?')})"
    except requests.exceptions.HTTPError as e:
        response = e.response
        status = response.status_code if response is not None else "?"
        text = response.text[:300] if response is not None else str(e)
        return f"DB: Erreur sauvegarde - HTTP {status}: {text}"
    except Exception as e:
        return f"DB: Erreur sauvegarde - {type(e).__name__}: {e}"


def _normalize_contact(contact: dict) -> dict:
    email = _normalize_email(
        contact.get("contact_email", "")
        or contact.get("email", "")
    )
    full_name = (
        contact.get("contact_name", "")
        or contact.get("name", "")
        or " ".join(
            part for part in [
                str(contact.get("prenom", "") or contact.get("first_name", "")).strip(),
                str(contact.get("nom", "") or contact.get("last_name", "")).strip(),
            ]
            if part
        ).strip()
    )
    first_name, last_name = _split_contact_name(full_name)
    contact_first_name = (
        contact.get("contact_first_name", "")
        or contact.get("firstName", "")
        or contact.get("prenom", "")
        or contact.get("first_name", "")
        or first_name
    )
    contact_last_name = (
        contact.get("contact_last_name", "")
        or contact.get("lastName", "")
        or contact.get("nom", "")
        or contact.get("last_name", "")
        or last_name
    )
    company_url = (
        contact.get("company_url", "")
        or contact.get("website_url", "")
        or contact.get("websiteUrl", "")
    )
    company_domain = (
        contact.get("company_domain", "")
        or contact.get("domain", "")
        or _normalize_domain(company_url)
    )
    if not company_domain and email and "@" in email:
        company_domain = email.split("@", 1)[1]

    return {
        "company_name": contact.get("company_name", "") or contact.get("entreprise", "") or contact.get("company", ""),
        "company_domain": company_domain,
        "company_url": company_url,
        "contact_name": full_name,
        "contact_first_name": str(contact_first_name).strip(),
        "contact_last_name": str(contact_last_name).strip(),
        "contact_email": email,
        "contact_title": contact.get("contact_title", "") or contact.get("title", "") or contact.get("titre", ""),
        "contact_specialty": contact.get("contact_specialty", "") or contact.get("specialty", "") or contact.get("specialite", ""),
        "contact_phone": contact.get("contact_phone", "") or contact.get("phone", "") or contact.get("telephone", ""),
        "contact_linkedin": contact.get("contact_linkedin", "") or contact.get("linkedin", ""),
        "email_status": contact.get("email_status", "") or contact.get("emailStatus", ""),
        "source": contact.get("source", "") or "save_enrichment",
        "quality_score": contact.get("quality_score", contact.get("qualityScore")),
        "quality_reason": contact.get("quality_reason", "") or contact.get("qualityReason", ""),
        "is_decision_maker": bool(contact.get("is_decision_maker", contact.get("isDecisionMaker", False))),
        "contact_city": (
            contact.get("contact_city", "")
            or contact.get("city", "")
            or contact.get("ville", "")
        ),
        "city_evidence": contact.get("city_evidence", ""),
    }


@tool
def save_enrichment(contacts_json: str) -> str:
    """Sauvegarde les contacts enrichis en base de donnees."""
    raise_if_cancelled()

    try:
        contacts = json.loads(contacts_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide - {e}"

    if not isinstance(contacts, list) or not contacts:
        return "Erreur: Le JSON doit contenir une liste non-vide de contacts."

    ctx = _ctx()
    target_city = str(ctx.get("location") or "")

    normalized_contacts = [_normalize_contact(contact) for contact in contacts]

    filtered_contacts: list[dict] = []
    rejected_no_email = 0
    rejected_city = 0

    for contact in normalized_contacts:
        email = contact.get("contact_email", "")
        if not email:
            rejected_no_email += 1
            continue

        contact_city = str(contact.get("contact_city") or "")
        if target_city and not _city_matches(target_city, contact_city):
            rejected_city += 1
            continue

        filtered_contacts.append(contact)

    if not filtered_contacts:
        details = []
        if rejected_no_email:
            details.append(f"{rejected_no_email} sans email")
        if rejected_city:
            details.append(f"{rejected_city} hors ville ou ville non confirmee")
        detail_text = ", ".join(details) if details else "aucun contact exploitable"
        city_note = f" (ville cible: {target_city})" if target_city else ""
        return (
            f"Aucun contact sauvegarde: {detail_text}{city_note}. "
            f"Continue avec Perplexity, crawl_url, puis verification email avant de rappeler save_enrichment."
        )

    company_domain = ""
    company_url = ""
    company_name = ""
    for c in filtered_contacts:
        domain = c.get("company_domain", "") or _normalize_domain(c.get("company_url", ""))
        if domain:
            company_domain = domain
        if not company_url and c.get("company_url", ""):
            company_url = c.get("company_url", "")
        if not company_name and c.get("company_name", ""):
            company_name = c.get("company_name", "")
        if company_domain and company_url and company_name:
            break

    db_result = _save_to_db(filtered_contacts, company_domain, company_url, company_name)
    if not db_result:
        return "Aucun contact sauvegarde."

    rejects = []
    if rejected_no_email:
        rejects.append(f"{rejected_no_email} sans email")
    if rejected_city:
        rejects.append(f"{rejected_city} hors ville")
    rejects_text = f" Rejets: {', '.join(rejects)}." if rejects else ""
    return f"{db_result}{rejects_text}"


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
