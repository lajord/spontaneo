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
    target_count: int | None = None,
) -> None:
    set_run_context(
        user_id=user_id,
        job_id=job_id,
        campaign_id=campaign_id,
        secteur=secteur,
        job_title=job_title,
        location=location,
        target_count=target_count,
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


def _normalize_candidate(company: dict) -> dict | None:
    name = str(company.get("name", "") or "").strip()
    website_url = str(
        company.get("websiteUrl")
        or company.get("website_url")
        or company.get("website")
        or company.get("url")
        or ""
    ).strip()
    if not name or not website_url:
        return None

    domain = str(company.get("domain", "") or "").strip() or _normalize_domain(website_url)

    return {
        "name": name,
        "websiteUrl": website_url,
        "domain": domain or None,
        "city": str(company.get("city", "") or "").strip(),
        "description": str(company.get("description", "") or "").strip(),
        "source": str(company.get("source", "") or "").strip(),
    }


def normalize_candidates(companies: list[dict]) -> tuple[list[dict], int]:
    normalized_companies = []
    rejected = 0

    for company in companies:
        normalized = _normalize_candidate(company)
        if normalized is None:
            rejected += 1
            continue
        normalized_companies.append(normalized)

    return normalized_companies, rejected


def _candidate_to_row(candidate: dict) -> dict:
    return {
        "id": candidate.get("id", ""),
        "name": candidate.get("name", ""),
        "websiteUrl": candidate.get("websiteUrl", ""),
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


def save_candidates_batch(companies: list[dict]) -> dict:
    ctx = _ctx()
    user_id = ctx.get("user_id")
    job_id = ctx.get("job_id")
    campaign_id = ctx.get("campaign_id")
    if not user_id or not job_id:
        return {
            "ok": False,
            "error": "Erreur: Contexte incomplet. user_id et job_id sont requis.",
        }

    normalized_companies, rejected = normalize_candidates(companies)
    if not normalized_companies:
        return {
            "ok": False,
            "error": (
                "Erreur: aucune entreprise valide a sauvegarder. "
                "Chaque entree doit au minimum contenir `name` et `websiteUrl`."
            ),
            "rejected": rejected,
        }

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
        return {
            "ok": True,
            "added": data.get("added", 0),
            "total": data.get("total", 0),
            "duplicates": data.get("duplicates", 0),
            "rejected": rejected,
            "saved": len(normalized_companies),
        }
    except requests.exceptions.ConnectionError:
        return {
            "ok": False,
            "error": "Erreur: Impossible de joindre l'API web. Verifie que WEB_URL est correct.",
            "rejected": rejected,
        }
    except requests.exceptions.HTTPError as e:
        return {
            "ok": False,
            "error": f"Erreur HTTP {e.response.status_code}: {e.response.text[:300]}",
            "rejected": rejected,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Erreur lors de la sauvegarde: {type(e).__name__}: {e}",
            "rejected": rejected,
        }


def format_save_candidates_result(result: dict) -> str:
    if not result.get("ok"):
        error = result.get("error", "Erreur inconnue.")
        rejected = result.get("rejected", 0)
        reject_note = f" (rejetees: {rejected})" if rejected else ""
        return f"{error}{reject_note}"

    reject_note = f", rejetees: {result.get('rejected', 0)}" if result.get("rejected", 0) else ""
    return (
        f"{result.get('added', 0)} nouvelles entreprises ajoutees "
        f"(total: {result.get('total', '?')}, "
        f"doublons ignores: {result.get('duplicates', 0)}{reject_note}).\n"
        f"Fichier : base de donnees"
    )


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

    result = save_candidates_batch(companies)
    return format_save_candidates_result(result)


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
        "id": row.get("id"),
        "name": row.get("name"),
        "websiteUrl": row.get("websiteUrl"),
        "domain": row.get("domain"),
        "city": row.get("city"),
        "source": row.get("source"),
    }, ensure_ascii=False)


