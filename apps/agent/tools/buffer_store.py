import json
import os
import re
from langchain_core.tools import tool

from config import AGENT3_TARGET_CONTACTS
from runtime import get_context_value, raise_if_cancelled


OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUFFER_DIR = os.path.join(OUTPUT_DIR, "buffers")

_EMAIL_STATUS_RANK = {
    "": 0,
    "unknown": 1,
    "invalid": 2,
    "catchall": 3,
    "valid": 4,
}


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:80]


def _buffer_path(company_name: str) -> str:
    job_id = str(get_context_value("job_id", "shared"))
    job_dir = os.path.join(BUFFER_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return os.path.join(job_dir, f"buffer_{_slugify(company_name)}.jsonl")


def _read_buffer(company_name: str) -> list[dict]:
    path = _buffer_path(company_name)
    if not os.path.exists(path):
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _write_buffer(company_name: str, entries: list[dict]) -> None:
    path = _buffer_path(company_name)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _find_matching_index(entry: dict, existing: list[dict]) -> int | None:
    email = _normalize_email(entry.get("email", ""))
    if email:
        for index, item in enumerate(existing):
            if _normalize_email(item.get("email", "")) == email:
                return index

    name = _normalize_name(entry.get("name", ""))
    if name:
        for index, item in enumerate(existing):
            if _normalize_name(item.get("name", "")) == name:
                return index

    return None


def _merge_sources(existing_source: str, incoming_source: str) -> str:
    parts = []
    for chunk in [existing_source, incoming_source]:
        for item in str(chunk or "").split(" + "):
            item = item.strip()
            if item and item not in parts:
                parts.append(item)
    return " + ".join(parts)


def _merge_entry(existing: dict, incoming: dict) -> tuple[dict, bool]:
    merged = dict(existing)
    changed = False

    for key, value in incoming.items():
        if key == "source":
            merged_source = _merge_sources(existing.get("source", ""), value)
            if merged_source != merged.get("source", ""):
                merged["source"] = merged_source
                changed = True
            continue

        if key == "email_status":
            current_rank = _EMAIL_STATUS_RANK.get(str(existing.get("email_status", "")).lower(), 0)
            incoming_rank = _EMAIL_STATUS_RANK.get(str(value or "").lower(), 0)
            if incoming_rank > current_rank:
                merged["email_status"] = value
                changed = True
            continue

        if value and not merged.get(key):
            merged[key] = value
            changed = True

    return merged, changed


def cleanup_buffer(company_name: str) -> None:
    path = _buffer_path(company_name)
    if os.path.exists(path):
        os.remove(path)


@tool
def save_to_buffer(company_name: str, findings_json: str) -> str:
    """Enregistre des trouvailles dans le buffer de l'entreprise."""
    raise_if_cancelled()

    try:
        findings = json.loads(findings_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide - {e}"

    if not isinstance(findings, list):
        return "Erreur: Le JSON doit contenir une liste de trouvailles."
    if not findings:
        return "Aucune trouvaille a ajouter. Continue tes recherches."

    existing = _read_buffer(company_name)
    added = 0
    updated = 0
    ignored = 0

    for entry in findings:
        match_index = _find_matching_index(entry, existing)
        if match_index is None:
            existing.append(entry)
            added += 1
            continue

        merged, changed = _merge_entry(existing[match_index], entry)
        existing[match_index] = merged
        if changed:
            updated += 1
        else:
            ignored += 1

    _write_buffer(company_name, existing)

    total = len(existing)
    with_email = sum(1 for e in existing if e.get("email"))
    verified = sum(1 for e in existing if e.get("email_status") in ("valid", "catchall"))

    return (
        f"{added} nouvelles entrees ajoutees, {updated} enrichies, {ignored} ignorees.\n"
        f"Buffer total : {total} entrees, {with_email} avec email, {verified} verifiees.\n"
        f"Continue tant que tu n'as pas assez d'emails qualifies et confirmes sur la bonne ville."
    )


@tool
def evaluate_findings(company_name: str) -> str:
    """Lit le buffer complet et presente toutes les trouvailles pour evaluation."""
    entries = _read_buffer(company_name)
    target_city = str(get_context_value("location", "") or "")

    if not entries:
        return (
            f"=== BILAN POUR {company_name} ===\n\n"
            f"Aucune trouvaille dans le buffer.\n"
            f"Relance tes recherches avec d'autres angles ou appelle save_enrichment "
            f"avec une liste vide si tu as epuise toutes les options."
        )

    lines = []
    for i, e in enumerate(entries, 1):
        name = e.get("name", "-")
        title = e.get("title", "-")
        email = e.get("email", "-")
        source = e.get("source", "?")
        status = e.get("email_status", "")
        city = e.get("city") or e.get("contact_city") or "-"

        parts = [f"{i}. {name}"]
        if title != "-":
            parts.append(f"| {title}")
        if city != "-":
            parts.append(f"| ville: {city}")
        if email != "-":
            status_str = f" [{status}]" if status else ""
            parts.append(f"| {email}{status_str}")
        parts.append(f"| source: {source}")
        lines.append(" ".join(parts))

    total = len(entries)
    with_email = sum(1 for e in entries if e.get("email"))
    verified_valid = sum(1 for e in entries if e.get("email_status") == "valid")
    verified_catchall = sum(1 for e in entries if e.get("email_status") == "catchall")
    target = AGENT3_TARGET_CONTACTS
    city_line = f"Ville cible : {target_city}\n" if target_city else ""

    summary = "\n".join(lines)

    return (
        f"=== BILAN POUR {company_name} ===\n\n"
        f"{summary}\n\n"
        f"--- STATS ---\n"
        f"{city_line}"
        f"Total : {total} entrees\n"
        f"Avec email : {with_email}\n"
        f"Email verifie (valid) : {verified_valid}\n"
        f"Email verifie (catchall) : {verified_catchall}\n"
        f"Objectif : {target} contacts decideurs avec email nominatif et bonne ville\n\n"
        f"--- ACTION FINALE ---\n"
        f"Sauvegarde MAINTENANT avec save_enrichment :\n"
        f"1. Tous les contacts decideurs avec email nominatif verifie (valid/catchall).\n"
        f"2. Si MOINS de {target} emails nominatifs verifies, ajoute un email generique (contact@, info@) trouve sur le site.\n"
        f"3. Sauvegarde TOUJOURS au moins 1 contact, meme generique.\n\n"
        f"Puis appelle read_enrichment_summary. TERMINE, pas de boucle."
    )
