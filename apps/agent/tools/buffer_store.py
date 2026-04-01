import json
import os
import re
from langchain_core.tools import tool

from config import AGENT3_TARGET_CONTACTS
from runtime import get_context_value, raise_if_cancelled


# Dossier de sortie = dossier parent (apps/agent/)
OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUFFER_DIR = os.path.join(OUTPUT_DIR, "buffers")


def _slugify(name: str) -> str:
    """Transforme un nom d'entreprise en slug pour le nom de fichier."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:80]


def _buffer_path(company_name: str) -> str:
    """Retourne le chemin du fichier buffer pour une entreprise."""
    job_id = str(get_context_value("job_id", "shared"))
    job_dir = os.path.join(BUFFER_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return os.path.join(job_dir, f"buffer_{_slugify(company_name)}.jsonl")


def _read_buffer(company_name: str) -> list[dict]:
    """Lit toutes les entrees du buffer."""
    path = _buffer_path(company_name)
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def _is_duplicate(entry: dict, existing: list[dict]) -> bool:
    """Verifie si une entree existe deja dans le buffer."""
    email = (entry.get("email") or "").lower().strip()
    if email:
        return any(
            (e.get("email") or "").lower().strip() == email
            for e in existing
        )
    name = (entry.get("name") or "").lower().strip()
    if name:
        return any(
            (e.get("name") or "").lower().strip() == name
            for e in existing
        )
    return False


def cleanup_buffer(company_name: str) -> None:
    """Supprime le fichier buffer d'une entreprise."""
    path = _buffer_path(company_name)
    if os.path.exists(path):
        os.remove(path)


@tool
def save_to_buffer(company_name: str, findings_json: str) -> str:
    """Enregistre des trouvailles dans le fichier tampon de l'entreprise.

    Appelle cet outil APRES chaque phase de recherche (crawl, Perplexity,
    Apollo, NeverBounce) pour sauvegarder ce que tu as trouve.
    Les donnees sont AJOUTEES au buffer (jamais ecrasees).
    Les doublons (meme email ou meme nom) sont automatiquement filtres.

    Args:
        company_name: Nom de l'entreprise enrichie.
        findings_json: JSON string contenant une liste de trouvailles.
            Chaque entree peut contenir : name, title, email, phone,
            linkedin, source, email_status.
            Exemples de source : "crawl_homepage", "crawl_equipe",
            "perplexity", "apollo_search", "apollo_match", "neverbounce".

    Returns:
        Resume du buffer apres ajout avec instructions pour la suite.
    """
    raise_if_cancelled()

    try:
        findings = json.loads(findings_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide — {e}"

    if not isinstance(findings, list):
        return "Erreur: Le JSON doit contenir une liste de trouvailles."

    if not findings:
        return "Aucune trouvaille a ajouter. Continue tes recherches."

    # Lire le buffer existant
    existing = _read_buffer(company_name)

    # Filtrer les doublons et ajouter
    path = _buffer_path(company_name)
    added = 0
    with open(path, "a", encoding="utf-8") as f:
        for entry in findings:
            if _is_duplicate(entry, existing):
                continue
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            existing.append(entry)
            added += 1

    total = len(existing)
    with_email = sum(1 for e in existing if e.get("email"))
    verified = sum(1 for e in existing if e.get("email_status") in ("valid", "catchall"))

    return (
        f"{added} nouvelles entrees ajoutees (doublons ignores: {len(findings) - added}).\n"
        f"Buffer total : {total} entrees, {with_email} avec email, {verified} verifiees.\n"
        f"Continue tes recherches ou appelle evaluate_findings pour faire le bilan."
    )


@tool
def evaluate_findings(company_name: str) -> str:
    """Lit le buffer complet et presente toutes les trouvailles pour evaluation.

    Appelle cet outil APRES avoir explore toutes tes sources (crawl, Perplexity,
    Apollo, NeverBounce). Il te presente un bilan propre de tout ce que tu as
    trouve pour que tu puisses evaluer la qualite et decider de la suite.

    Args:
        company_name: Nom de l'entreprise enrichie.

    Returns:
        Bilan formate de toutes les trouvailles avec instructions de decision.
    """
    entries = _read_buffer(company_name)

    if not entries:
        return (
            f"=== BILAN POUR {company_name} ===\n\n"
            f"Aucune trouvaille dans le buffer.\n"
            f"Relance tes recherches avec d'autres angles ou "
            f"appelle save_enrichment avec une liste vide si tu as epuise toutes les options."
        )

    # Formater chaque entree
    lines = []
    for i, e in enumerate(entries, 1):
        name = e.get("name", "—")
        title = e.get("title", "—")
        email = e.get("email", "—")
        phone = e.get("phone", "—")
        linkedin = e.get("linkedin", "—")
        source = e.get("source", "?")
        status = e.get("email_status", "")

        parts = [f"{i}. {name}"]
        if title != "—":
            parts.append(f"| {title}")
        if email != "—":
            status_str = f" [{status}]" if status else ""
            parts.append(f"| {email}{status_str}")
        if phone != "—":
            parts.append(f"| tel: {phone}")
        if linkedin != "—":
            parts.append(f"| LinkedIn: {linkedin}")
        parts.append(f"| source: {source}")

        lines.append(" ".join(parts))

    # Stats
    total = len(entries)
    with_email = sum(1 for e in entries if e.get("email"))
    verified_valid = sum(1 for e in entries if e.get("email_status") == "valid")
    verified_catchall = sum(1 for e in entries if e.get("email_status") == "catchall")
    target = AGENT3_TARGET_CONTACTS

    summary = "\n".join(lines)

    return (
        f"=== BILAN POUR {company_name} ===\n\n"
        f"{summary}\n\n"
        f"--- STATS ---\n"
        f"Total : {total} entrees\n"
        f"Avec email : {with_email}\n"
        f"Email verifie (valid) : {verified_valid}\n"
        f"Email verifie (catchall) : {verified_catchall}\n"
        f"Objectif : {target} contacts decideurs avec email verifie\n\n"
        f"--- DECISION ---\n"
        f"Analyse chaque contact ci-dessus :\n"
        f"- Est-ce un DECIDEUR (associe, partner, DG, directeur, responsable) ?\n"
        f"- Son email est-il NOMINATIF (prenom.nom@...) et non generique (info@, contact@) ?\n"
        f"- Son email est-il VERIFIE (valid ou catchall) ?\n\n"
        f"Si tu as au moins {target} contacts decideurs avec email qualifie :\n"
        f"→ Sauvegarde-les avec save_enrichment et ARRETE.\n\n"
        f"Sinon :\n"
        f"→ Relance une recherche avec d'autres angles (autres mots-cles, autres sources).\n"
        f"→ Puis appelle a nouveau save_to_buffer et evaluate_findings."
    )
