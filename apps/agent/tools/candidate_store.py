import csv
import json
import os
from langchain_core.tools import tool

# Dossier de sortie = dossier parent (apps/agent/)
OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATES_CSV = os.path.join(OUTPUT_DIR, "candidates.csv")
VERIFIED_CSV = os.path.join(OUTPUT_DIR, "verified.csv")

CANDIDATES_COLUMNS = [
    "name", "website_url", "domain", "city", "description", "source", "status",
]

VERIFIED_COLUMNS = [
    "name", "website_url", "city", "source",
    "specialty_confirmed", "specialties_found", "relevance_score", "relevance_reason",
    "siren", "company_activity", "is_hiring",
]


def _normalize(name: str) -> str:
    """Normalise un nom pour la déduplication."""
    return name.lower().strip().replace("  ", " ")


def _normalize_domain(url: str) -> str:
    """Extrait le domaine normalisé d'une URL."""
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://www.", "http://www.", "https://", "http://"]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


@tool
def save_candidates(companies_json: str) -> str:
    """Sauvegarde la liste d'entreprises candidates dans un fichier CSV.

    Utilise cet outil APRES chaque recherche (Apollo, web_search, Google Maps).
    Les resultats seront dedupliques automatiquement par nom et domaine web.
    Chaque entreprise est marquee comme "pending" pour la phase de verification.

    Args:
        companies_json: JSON string contenant une liste d'entreprises.
            Chaque entreprise doit avoir au minimum : name, website_url, city, source.

    Returns:
        Message indiquant combien d'entreprises ont ete sauvegardees (apres deduplication).
    """
    try:
        companies = json.loads(companies_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide — {e}"

    if not isinstance(companies, list) or not companies:
        return "Erreur: Le JSON doit contenir une liste non-vide d'entreprises."

    # Lire les candidats existants pour ne pas les écraser
    existing = []
    seen = set()
    if os.path.exists(CANDIDATES_CSV):
        with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            existing = list(reader)
        for row in existing:
            name = _normalize(row.get("name", ""))
            domain = _normalize_domain(row.get("website_url", ""))
            key = (name, domain) if domain else (name,)
            seen.add(key)

    # Ajouter les nouveaux (dédupliqués)
    added = 0
    for company in companies:
        name = _normalize(company.get("name", ""))
        domain = _normalize_domain(company.get("website_url") or company.get("url", ""))
        key = (name, domain) if domain else (name,)

        if key not in seen:
            seen.add(key)
            existing.append({
                "name": company.get("name", ""),
                "website_url": company.get("website_url") or company.get("url", ""),
                "domain": domain,
                "city": company.get("city", ""),
                "description": (company.get("description") or "")[:300],
                "source": company.get("source", ""),
                "status": "pending",
            })
            added += 1

    # Écrire le CSV complet
    with open(CANDIDATES_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATES_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(existing)

    total = len(existing)
    return (
        f"{added} nouvelles entreprises ajoutees (total: {total}, dedupliquees depuis {len(companies)} bruts).\n"
        f"Fichier : {CANDIDATES_CSV}"
    )


@tool
def read_candidates_summary() -> str:
    """Retourne un resume de l'etat actuel du fichier de candidats.

    Utilise cet outil pour savoir combien d'entreprises ont deja ete collectees,
    combien sont en attente de verification, et combien ont ete traitees.
    Appelle-le au debut ou a la fin de ton travail pour suivre la progression.

    Returns:
        JSON avec total, pending, done counts.
    """
    if not os.path.exists(CANDIDATES_CSV):
        return json.dumps({
            "total": 0,
            "pending": 0,
            "done": 0,
            "message": "Aucun candidat. Le fichier CSV n'existe pas encore.",
        })

    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    total = len(rows)
    pending = sum(1 for r in rows if r.get("status", "").strip() == "pending")
    done = total - pending

    return json.dumps({
        "total": total,
        "pending": pending,
        "done": done,
        "message": f"{total} entreprises au total ({pending} en attente, {done} traitees).",
    })


@tool
def read_next_candidate() -> str:
    """Lit la prochaine entreprise candidate a verifier depuis le fichier CSV.

    Retourne la prochaine entreprise dont le status est "pending".
    Si toutes les entreprises ont ete traitees, retourne "DONE".

    Returns:
        JSON de la prochaine entreprise a verifier, ou "DONE" si toutes sont traitees.
    """
    if not os.path.exists(CANDIDATES_CSV):
        return json.dumps({"error": "Fichier candidates.csv introuvable. Lance d'abord la phase de collecte."})

    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    for row in rows:
        if row.get("status", "").strip() == "pending":
            return json.dumps(row, ensure_ascii=False)

    return "DONE"


@tool
def save_verification(
    candidate_name: str,
    specialty_confirmed: bool,
    relevance_score: int,
    relevance_reason: str,
    specialties_found: str = "",
    siren: str = "",
    company_activity: str = "",
    is_hiring: bool = None,
    website_url: str = "",
    city: str = "",
    source: str = "",
) -> str:
    """Sauvegarde le résultat de la vérification d'un cabinet et le marque comme traité.

    Utilise cet outil APRES avoir crawlé et analysé le site d'un cabinet avec crawl_url.
    Écrit le résultat dans verified.csv et marque le cabinet comme "done" dans candidates.csv.

    Args:
        candidate_name: Nom exact du cabinet (tel que dans candidates.csv)
        specialty_confirmed: True si le cabinet exerce bien la spécialité, False sinon
        relevance_score: Score de pertinence de 0 à 10 (issu du crawl)
        relevance_reason: Explication factuelle du score
        specialties_found: Spécialités effectivement trouvées sur le site
        siren: Numéro SIREN si trouvé lors du crawl
        company_activity: Description de l'activité du cabinet
        is_hiring: True si le cabinet recrute, False sinon, None si inconnu
        website_url: URL du site web
        city: Ville du cabinet
        source: Source d'origine (apollo, perplexity_web_search)

    Returns:
        Message de confirmation.
    """
    # 1. Écrire dans verified.csv (append)
    file_exists = os.path.exists(VERIFIED_CSV)
    row = {
        "name": candidate_name,
        "website_url": website_url,
        "city": city,
        "source": source,
        "specialty_confirmed": str(specialty_confirmed),
        "specialties_found": specialties_found,
        "relevance_score": str(relevance_score),
        "relevance_reason": relevance_reason,
        "siren": siren,
        "company_activity": company_activity,
        "is_hiring": str(is_hiring) if is_hiring is not None else "",
    }

    with open(VERIFIED_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=VERIFIED_COLUMNS, delimiter=";")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    # 2. Marquer comme "done" dans candidates.csv
    if os.path.exists(CANDIDATES_CSV):
        with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            rows = list(reader)

        name_normalized = _normalize(candidate_name)
        for row in rows:
            if _normalize(row.get("name", "")) == name_normalized:
                row["status"] = "done"

        with open(CANDIDATES_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CANDIDATES_COLUMNS, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    status = "CONFIRMÉ" if specialty_confirmed else "NON CONFIRMÉ"
    return json.dumps({
        "name": candidate_name,
        "status": status,
        "score": relevance_score,
        "reason": relevance_reason,
        "specialties": specialties_found,
    }, ensure_ascii=False)


@tool
def append_candidates(companies_json: str) -> str:
    """Ajoute des entreprises candidates au fichier CSV existant.

    Utilise cet outil pour ajouter des entreprises trouvees lors d'une recherche complementaire.
    Les doublons avec les candidats existants sont automatiquement filtres.

    Args:
        companies_json: JSON string contenant une liste d'entreprises a ajouter.
            Chaque entreprise doit avoir au minimum : name, website_url, city, source.

    Returns:
        Message indiquant combien de nouvelles entreprises ont ete ajoutees.
    """
    try:
        new_companies = json.loads(companies_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide — {e}"

    if not isinstance(new_companies, list) or not new_companies:
        return "Erreur: Le JSON doit contenir une liste non-vide d'entreprises."

    # Lire les candidats existants
    existing = []
    seen = set()
    if os.path.exists(CANDIDATES_CSV):
        with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            existing = list(reader)
        for row in existing:
            name = _normalize(row.get("name", ""))
            domain = _normalize_domain(row.get("website_url", ""))
            key = (name, domain) if domain else (name,)
            seen.add(key)

    # Ajouter les nouveaux (dédupliqués)
    added = 0
    for company in new_companies:
        name = _normalize(company.get("name", ""))
        domain = _normalize_domain(company.get("website_url") or company.get("url", ""))
        key = (name, domain) if domain else (name,)

        if key not in seen:
            seen.add(key)
            existing.append({
                "name": company.get("name", ""),
                "website_url": company.get("website_url") or company.get("url", ""),
                "domain": domain,
                "city": company.get("city", ""),
                "description": (company.get("description") or "")[:300],
                "source": company.get("source", "deep_search"),
                "status": "pending",
            })
            added += 1

    # Réécrire le fichier complet
    with open(CANDIDATES_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATES_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(existing)

    total = len(existing)
    return f"{added} nouvelles entreprises ajoutees (total: {total}). {len(new_companies) - added} doublons ignores."
