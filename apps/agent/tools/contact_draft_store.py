import json
import os
import re

import requests
from langchain_core.tools import tool

from runtime import get_run_context, raise_if_cancelled

_WEB_URL = os.getenv("WEB_URL", "http://web:3000")
_API_ENDPOINT = f"{_WEB_URL}/api/agent/contact-drafts"

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


def _ctx() -> dict:
    return get_run_context()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _split_name(full_name: str) -> tuple[str, str]:
    cleaned = _normalize_text(full_name)
    if not cleaned:
        return "", ""
    parts = cleaned.split(" ")
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _infer_contact_type(email: str, explicit_type: str) -> str:
    cleaned = str(explicit_type or "").strip().lower()
    if cleaned in {"personal", "generic"}:
        return cleaned

    normalized_email = _normalize_email(email)
    if normalized_email and "@" in normalized_email:
        local_part = normalized_email.split("@", 1)[0]
        if local_part in _GENERIC_EMAIL_PREFIXES:
            return "generic"
    return "personal"


def _normalize_draft(entry: dict) -> tuple[dict | None, str | None]:
    if not isinstance(entry, dict):
        return None, "Chaque entree doit etre un objet JSON."

    agent_candidate_id = _normalize_text(entry.get("agentCandidateId", ""))
    if not agent_candidate_id:
        return None, "`agentCandidateId` est requis."

    full_name = _normalize_text(entry.get("name", ""))
    first_name = _normalize_text(entry.get("firstName", ""))
    last_name = _normalize_text(entry.get("lastName", ""))

    if not full_name:
        full_name = _normalize_text(" ".join(part for part in [first_name, last_name] if part))

    if not full_name:
        return None, "`name` est requis."

    split_first, split_last = _split_name(full_name)
    if not first_name:
        first_name = split_first
    if not last_name:
        last_name = split_last

    email = _normalize_email(entry.get("email", ""))
    normalized = {
        "agentCandidateId": agent_candidate_id,
        "name": full_name,
        "firstName": first_name or None,
        "lastName": last_name or None,
        "email": email or None,
        "title": _normalize_text(entry.get("title", "")) or None,
        "specialty": _normalize_text(entry.get("specialty", "")) or None,
        "city": _normalize_text(entry.get("city", "")) or None,
        "contactType": _infer_contact_type(email, entry.get("contactType", "")),
        "isTested": bool(entry.get("isTested", False)),
        "sourceStage": _normalize_text(entry.get("sourceStage", "")) or "3A",
        "sourceTool": _normalize_text(entry.get("sourceTool", "")) or None,
        "sourceUrl": _normalize_text(entry.get("sourceUrl", "")) or None,
    }
    return normalized, None


def _draft_to_row(draft: dict) -> dict:
    return {
        "id": draft.get("id", ""),
        "agentCandidateId": draft.get("agentCandidateId", ""),
        "name": draft.get("name", ""),
        "firstName": draft.get("firstName", ""),
        "lastName": draft.get("lastName", ""),
        "email": draft.get("email", ""),
        "title": draft.get("title", ""),
        "specialty": draft.get("specialty", ""),
        "city": draft.get("city", ""),
        "contactType": draft.get("contactType", ""),
        "isTested": draft.get("isTested", False),
        "sourceStage": draft.get("sourceStage", ""),
        "sourceTool": draft.get("sourceTool", ""),
        "sourceUrl": draft.get("sourceUrl", ""),
    }


def get_contact_draft_rows(agent_candidate_id: str = "") -> list[dict]:
    ctx = _ctx()
    user_id = ctx.get("user_id")
    job_id = ctx.get("job_id")
    if not user_id or not job_id:
        return []

    params = {"jobId": job_id}
    if agent_candidate_id:
        params["agentCandidateId"] = agent_candidate_id

    try:
        resp = requests.get(_API_ENDPOINT, params=params, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return [_draft_to_row(draft) for draft in resp.json().get("drafts", [])]
    except Exception:
        return []


def get_pending_personal_drafts(agent_candidate_id: str) -> list[dict]:
    rows = get_contact_draft_rows(agent_candidate_id)
    return [
        row for row in rows
        if row.get("contactType") == "personal"
        and (not row.get("email") or not row.get("specialty"))
    ]


def get_personal_drafts(agent_candidate_id: str) -> list[dict]:
    rows = get_contact_draft_rows(agent_candidate_id)
    return [row for row in rows if row.get("contactType") == "personal"]


def get_personal_drafts_without_email(agent_candidate_id: str) -> list[dict]:
    rows = get_personal_drafts(agent_candidate_id)
    return [row for row in rows if not row.get("email")]


def save_contact_drafts_batch(drafts: list[dict]) -> dict:
    ctx = _ctx()
    user_id = ctx.get("user_id")
    job_id = ctx.get("job_id")
    if not user_id or not job_id:
        return {"ok": False, "error": "Erreur: Contexte incomplet. user_id et job_id sont requis."}

    normalized_drafts: list[dict] = []
    errors: list[str] = []

    for index, draft in enumerate(drafts, 1):
        normalized, error = _normalize_draft(draft)
        if error:
            errors.append(f"entree {index}: {error}")
            continue
        normalized_drafts.append(normalized)

    if not normalized_drafts:
        return {
            "ok": False,
            "error": "Erreur: aucun draft valide a sauvegarder.",
            "errors": errors[:5],
        }

    payload = {
        "jobId": job_id,
        "drafts": normalized_drafts,
    }

    try:
        resp = requests.post(_API_ENDPOINT, json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "ok": True,
            "added": data.get("added", 0),
            "updated": data.get("updated", 0),
            "ignored": data.get("ignored", 0),
            "rejected": data.get("rejected", 0) + max(0, len(errors)),
            "errors": errors[:5] + list(data.get("errors", [])[:5]),
            "saved": len(normalized_drafts),
        }
    except requests.exceptions.ConnectionError:
        return {
            "ok": False,
            "error": "Erreur: Impossible de joindre l'API web pour sauver les drafts.",
            "errors": errors[:5],
        }
    except requests.exceptions.HTTPError as e:
        return {
            "ok": False,
            "error": f"Erreur HTTP {e.response.status_code}: {e.response.text[:300]}",
            "errors": errors[:5],
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Erreur lors de la sauvegarde des drafts: {type(e).__name__}: {e}",
            "errors": errors[:5],
        }


def format_save_contact_drafts_result(result: dict) -> str:
    errors = result.get("errors", []) or []
    error_lines = "\n".join(f"- {msg}" for msg in errors[:5])

    if not result.get("ok"):
        base = result.get("error", "Erreur inconnue.")
        if error_lines:
            return (
                f"{base}\n"
                f"Erreurs detaillees:\n{error_lines}\n"
                "Corrige le JSON et rappelle immediatement save_contact_drafts avec le meme batch."
            )
        return f"{base}\nCorrige le JSON et rappelle immediatement save_contact_drafts avec le meme batch."

    summary = (
        f"Drafts sauvegardes: ajoutes={result.get('added', 0)}, "
        f"mis_a_jour={result.get('updated', 0)}, ignores={result.get('ignored', 0)}, "
        f"rejetes={result.get('rejected', 0)}."
    )
    if error_lines:
        return (
            f"{summary}\n"
            f"Erreurs detaillees:\n{error_lines}\n"
            "Corrige uniquement les entrees rejetees si elles sont importantes, puis continue le crawl."
        )
    return summary


@tool
def save_contact_drafts(drafts_json: str) -> str:
    """Sauvegarde des contacts intermediaires en base de donnees pour Agent 3A/3B/3C."""
    raise_if_cancelled()

    try:
        drafts = json.loads(drafts_json)
    except json.JSONDecodeError as e:
        return (
            f"Erreur: JSON invalide - {e}\n"
            "Corrige le JSON et rappelle immediatement save_contact_drafts avec le meme batch."
        )

    if not isinstance(drafts, list) or not drafts:
        return (
            "Erreur: Le JSON doit contenir une liste non-vide de drafts.\n"
            "Corrige le JSON et rappelle immediatement save_contact_drafts avec le meme batch."
        )

    result = save_contact_drafts_batch(drafts)
    return format_save_contact_drafts_result(result)


@tool
def read_pending_personal_drafts(agent_candidate_id: str) -> str:
    """Retourne les drafts personnels incomplets d'une entreprise (email ou specialite manquants)."""
    raise_if_cancelled()

    pending = get_pending_personal_drafts(agent_candidate_id)
    if not pending:
        return "[]"
    return json.dumps(pending, ensure_ascii=False)
