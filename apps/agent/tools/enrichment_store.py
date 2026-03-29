import csv
import json
import os
from langchain_core.tools import tool


# Dossier de sortie = dossier parent (apps/agent/)
OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICHED_CSV = os.path.join(OUTPUT_DIR, "enriched.csv")

ENRICHED_COLUMNS = [
    "company_name",
    "company_domain",
    "company_url",
    "contact_name",
    "contact_first_name",
    "contact_last_name",
    "contact_email",
    "contact_title",
    "contact_phone",
    "contact_linkedin",
    "email_status",
    "source",
]


def _normalize_email(email: str) -> str:
    """Normalise un email pour la deduplication."""
    return email.lower().strip() if email else ""


def _normalize_name(name: str) -> str:
    """Normalise un nom pour la deduplication."""
    return name.lower().strip().replace("  ", " ") if name else ""


@tool
def save_enrichment(contacts_json: str) -> str:
    """Sauvegarde les contacts enrichis dans le fichier enriched.csv.

    Utilise cet outil APRES avoir trouve et verifie des contacts
    pour une entreprise. Passe TOUS les contacts trouves pour
    cette entreprise en un seul appel.

    Les doublons sont automatiquement filtres par email.
    Si un contact n'a pas d'email, la deduplication se fait par (company_name + contact_name).

    Args:
        contacts_json: JSON string contenant une liste de contacts.
            Chaque contact doit avoir au minimum : company_name, contact_name.
            Champs recommandes : contact_email, contact_title, contact_first_name,
            contact_last_name, contact_phone, contact_linkedin, email_status, source,
            company_domain, company_url.

    Returns:
        Message indiquant combien de contacts ont ete sauvegardes (apres deduplication).
    """
    try:
        contacts = json.loads(contacts_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide — {e}"

    if not isinstance(contacts, list) or not contacts:
        return "Erreur: Le JSON doit contenir une liste non-vide de contacts."

    # Lire les contacts existants
    existing = []
    seen = set()
    if os.path.exists(ENRICHED_CSV):
        with open(ENRICHED_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            existing = list(reader)
        for row in existing:
            email = _normalize_email(row.get("contact_email", ""))
            if email:
                seen.add(("email", email))
            else:
                company = _normalize_name(row.get("company_name", ""))
                name = _normalize_name(row.get("contact_name", ""))
                seen.add(("name", company, name))

    # Ajouter les nouveaux (dedupliques)
    added = 0
    for contact in contacts:
        email = _normalize_email(contact.get("contact_email", ""))

        if email:
            key = ("email", email)
        else:
            company = _normalize_name(contact.get("company_name", ""))
            name = _normalize_name(contact.get("contact_name", ""))
            key = ("name", company, name)

        if key in seen:
            continue

        seen.add(key)
        existing.append({
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
        added += 1

    # Ecrire le CSV complet
    with open(ENRICHED_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ENRICHED_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(existing)

    total = len(existing)
    return (
        f"{added} nouveaux contacts ajoutes (total: {total}, "
        f"dedupliques depuis {len(contacts)} bruts).\n"
        f"Fichier : {ENRICHED_CSV}"
    )


@tool
def read_enrichment_summary() -> str:
    """Retourne un resume de l'etat actuel du fichier enriched.csv.

    Utilise cet outil pour verifier combien de contacts ont deja ete trouves,
    au total et par entreprise.

    Returns:
        JSON avec le nombre total de contacts et la ventilation par entreprise.
    """
    if not os.path.exists(ENRICHED_CSV):
        return json.dumps({
            "total": 0,
            "by_company": {},
            "message": "Aucun contact enrichi. Le fichier enriched.csv n'existe pas encore.",
        })

    with open(ENRICHED_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

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
