import json
import os
from datetime import datetime

import pandas as pd
from langchain_core.tools import tool


# Colonnes dans l'ordre souhaité pour l'export
EXPORT_COLUMNS = [
    "name",
    "websiteUrl",
    "domain",
    "industry",
    "city",
    "state",
    "country",
    "employee_count",
    "description",
    "phone",
    "linkedin_url",
    "tech_stack",
    "is_hiring",
    "relevance_score",
    "relevance_reason",
    "source",
    "verified_by_crawl",
    "founded_year",
]

# Labels français pour les en-têtes CSV
COLUMN_LABELS = {
    "name": "Entreprise",
    "websiteUrl": "Site Web",
    "domain": "Domaine",
    "industry": "Secteur",
    "city": "Ville",
    "state": "Région",
    "country": "Pays",
    "employee_count": "Nb Employés",
    "description": "Description",
    "phone": "Téléphone",
    "linkedin_url": "LinkedIn",
    "tech_stack": "Technologies",
    "is_hiring": "Recrute",
    "relevance_score": "Score Pertinence",
    "relevance_reason": "Raison Pertinence",
    "source": "Source",
    "verified_by_crawl": "Vérifié (crawl)",
    "founded_year": "Année Création",
}


@tool
def export_results(
    companies_json: str,
    output_format: str = "csv",
    filename: str = None,
) -> str:
    """Exporte la liste finale des entreprises en fichier CSV ou Excel.

    Utilise cet outil UNIQUEMENT quand tu as terminé la recherche et la vérification.
    Les entreprises seront triées par score de pertinence décroissant.

    Args:
        companies_json: JSON string contenant la liste des entreprises à exporter.
                        Chaque entreprise doit être un dict avec les champs:
                        name, websiteUrl, industry, city, relevance_score, source, etc.
        output_format: "csv" ou "xlsx" (défaut: "csv")
        filename: Nom du fichier sans extension (défaut: auto-généré avec la date)

    Returns:
        Message de succès avec le chemin du fichier, ou message d'erreur.
    """
    try:
        companies = json.loads(companies_json)
    except json.JSONDecodeError as e:
        return f"Erreur: JSON invalide - {e}"

    if not companies:
        return "Erreur: Liste d'entreprises vide, rien à exporter."

    if not isinstance(companies, list):
        return "Erreur: Le JSON doit contenir une liste d'entreprises."

    # Créer le DataFrame
    df = pd.DataFrame(companies)

    # Convertir les listes en strings pour le CSV (ex: tech_stack)
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )

    # Garder seulement les colonnes qui existent, dans l'ordre souhaité
    available_cols = [c for c in EXPORT_COLUMNS if c in df.columns]
    extra_cols = [c for c in df.columns if c not in EXPORT_COLUMNS]
    df = df[available_cols + extra_cols]

    # Renommer les colonnes en français
    df = df.rename(columns=COLUMN_LABELS)

    # Trier par score de pertinence décroissant
    score_label = COLUMN_LABELS.get("relevance_score", "relevance_score")
    if score_label in df.columns:
        df[score_label] = pd.to_numeric(df[score_label], errors="coerce").fillna(0)
        df = df.sort_values(by=score_label, ascending=False).reset_index(drop=True)

    # Générer le nom de fichier
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"entreprises_ciblees_{timestamp}"

    # Dossier de sortie = répertoire courant
    output_dir = os.getcwd()
    fmt = output_format.lower().strip()

    if fmt == "xlsx":
        filepath = os.path.join(output_dir, f"{filename}.xlsx")
        df.to_excel(filepath, index=False, engine="openpyxl")
    else:
        filepath = os.path.join(output_dir, f"{filename}.csv")
        df.to_csv(filepath, index=False, encoding="utf-8-sig")

    return (
        f"Export réussi ! {len(df)} entreprises exportées.\n"
        f"Fichier : {filepath}\n"
        f"Format : {fmt.upper()}\n"
        f"Colonnes : {', '.join(df.columns.tolist())}"
    )
