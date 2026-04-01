import json
import os
import requests
from langchain_core.tools import tool

from runtime import get_run_context, raise_if_cancelled, set_run_context

# URL du service Next.js web (pour l'API agent/candidates)
_WEB_URL = os.getenv("WEB_URL", "http://web:3000")
_API_ENDPOINT = f"{_WEB_URL}/api/agent/candidates"


def _headers() -> dict[str, str]:
    token = os.getenv("AGENT_INTERNAL_API_TOKEN") or os.getenv("CRON_SECRET")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {"X-Agent-Dev-Internal": "1"}


def set_agent_context(
    user_id: str,
    job_id: str | None = None,
    campaign_id: str | None = None,
    secteur: str | None = None,
    job_title: str | None = None,
    location: str | None = None,
) -> None:
    set_run_context(
        user_id=user_id,
        job_id=job_id,
        campaign_id=campaign_id,
        secteur=secteur,
        job_title=job_title,
        location=location,
    )


def _ctx() -> dict:
    return get_run_context()


def _normalize_domain(url: str) -> str:
    if not url:
        return ""
    value = url.lower().strip().rstrip("/")
    for prefix in ["https://www.", "http://www.", "https://", "http://"]:
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.split("/")[0]


def _normalize_company_payload(company: dict) -> dict:
    website = (
        company.get("websiteUrl")
        or company.get("website_url")
        or company.get("website")
        or company.get("url")
        or ""
    )
    domain = company.get("domain") or _normalize_domain(website)

    return {
        "name": company.get("name", ""),
        "websiteUrl": website or None,
        "domain": domain or None,
        "city": company.get("city", ""),
        "description": company.get("description", ""),
        "source": company.get("source", ""),
    }


def _candidate_to_row(candidate: dict) -> dict:
    return {
        "name": candidate.get("name", ""),
        "website_url": candidate.get("websiteUrl", ""),
        "domain": candidate.get("domain", ""),
        "city": candidate.get("city", ""),
        "description": candidate.get("description", ""),
        "source": candidate.get("source", ""),
        "status": candidate.get("status", ""),
    }


def get_candidates_rows() -> list[dict]:
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
        return [_candidate_to_row(c) for c in resp.json().get("candidates", [])]
    except Exception:
        return []


@tool
def save_candidates(companies_json: str) -> str:
    """Sauvegarde la liste d'entreprises candidates en base de donnees."""
    raise_if_cancelled()

    try:
        companies = json.loads(companies_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide — {e}"

    if not isinstance(companies, list) or not companies:
        return "Erreur: Le JSON doit contenir une liste non-vide d'entreprises."

    ctx = _ctx()
    user_id = ctx.get("user_id")
    job_id = ctx.get("job_id")
    campaign_id = ctx.get("campaign_id")
    if not user_id or not job_id:
        return "Erreur: Contexte incomplet. user_id et job_id sont requis."

    normalized_companies = [_normalize_company_payload(company) for company in companies]

    payload = {
        "jobId": job_id,
        "secteur": ctx.get("secteur"),
        "jobTitle": ctx.get("job_title"),
        "location": ctx.get("location"),
        "companies": normalized_companies,
    }
    if campaign_id:
        payload["campaignId"] = campaign_id

    try:
        resp = requests.post(_API_ENDPOINT, json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return (
            f"{data.get('added', 0)} nouvelles entreprises ajoutees "
            f"(total: {data.get('total', '?')}, "
            f"doublons ignores: {data.get('duplicates', 0)}).\n"
            f"Fichier : base de donnees"
        )
    except requests.exceptions.ConnectionError:
        return "Erreur: Impossible de joindre l'API web. Verifie que WEB_URL est correct."
    except requests.exceptions.HTTPError as e:
        return f"Erreur HTTP {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:
        return f"Erreur lors de la sauvegarde: {type(e).__name__}: {e}"


@tool
def read_candidates_summary() -> str:
    """Retourne un resume de l'etat actuel des candidats en base de donnees."""
    raise_if_cancelled()

    rows = get_candidates_rows()
    total = len(rows)
    pending = sum(1 for c in rows if c.get("status") == "pending")
    done = total - pending

    return json.dumps({
        "total": total,
        "pending": pending,
        "done": done,
        "message": f"{total} entreprises au total ({pending} en attente, {done} traitees).",
    })


@tool
def read_next_candidate() -> str:
    """Lit la prochaine entreprise candidate a enrichir depuis la base de donnees."""
    raise_if_cancelled()

    rows = get_candidates_rows()
    pending = [row for row in rows if row.get("status") == "pending"]
    if not pending:
        return "DONE"

    row = pending[0]
    return json.dumps({
        "name": row.get("name"),
        "website_url": row.get("website_url"),
        "domain": row.get("domain"),
        "city": row.get("city"),
        "source": row.get("source"),
    }, ensure_ascii=False)


