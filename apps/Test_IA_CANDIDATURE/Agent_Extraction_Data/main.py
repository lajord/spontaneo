"""
Agent de Recherche de Cabinets d'Avocats
========================================
Usage (depuis le dossier Agent_Extraction_Data):
    python main.py

Ou depuis Test_IA_CANDIDATURE:
    python -m Agent_Extraction_Data.main
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from agent.graph import run_pipeline

# ─── Mapping des 16 spécialités juridiques ───────────────────────────

SPECIALTIES = {
    1:  {
        "name_fr": "Contentieux des Affaires",
        "name_en": "Business Litigation",
        "keywords_en": ["business litigation", "commercial disputes", "trial lawyer"],
        "keywords_fr": ["contentieux des affaires", "litiges commerciaux"],
    },
    2:  {
        "name_fr": "Arbitrage",
        "name_en": "Arbitration",
        "keywords_en": ["arbitration", "international arbitration", "dispute resolution"],
        "keywords_fr": ["arbitrage", "arbitrage international"],
    },
    3:  {
        "name_fr": "Concurrence / Antitrust",
        "name_en": "Competition & Antitrust",
        "keywords_en": ["antitrust", "competition law", "merger control"],
        "keywords_fr": ["droit de la concurrence", "antitrust"],
    },
    4:  {
        "name_fr": "Distribution & Conso",
        "name_en": "Distribution & Consumer",
        "keywords_en": ["distribution law", "consumer protection", "retail law"],
        "keywords_fr": ["droit de la distribution", "droit de la consommation"],
    },
    5:  {
        "name_fr": "IP / IT",
        "name_en": "Intellectual Property & Tech",
        "keywords_en": ["intellectual property", "patent law", "IT law", "technology law"],
        "keywords_fr": ["propriété intellectuelle", "droit du numérique", "droit des nouvelles technologies"],
    },
    6:  {
        "name_fr": "Droit Fiscal",
        "name_en": "Tax Law",
        "keywords_en": ["tax law", "tax advisory", "fiscal law"],
        "keywords_fr": ["droit fiscal", "fiscalité"],
    },
    7:  {
        "name_fr": "Droit Boursier",
        "name_en": "Capital Markets",
        "keywords_en": ["capital markets", "securities law", "stock exchange law"],
        "keywords_fr": ["droit boursier", "marchés de capitaux"],
    },
    8:  {
        "name_fr": "Debt Finance",
        "name_en": "Debt Finance",
        "keywords_en": ["debt finance", "loan agreements", "structured finance"],
        "keywords_fr": ["financement de dette", "financement structuré"],
    },
    9:  {
        "name_fr": "Corporate M&A / Fusions-Acquisitions",
        "name_en": "Corporate M&A",
        "keywords_en": ["mergers acquisitions", "M&A", "corporate law"],
        "keywords_fr": ["fusions-acquisitions", "droit des sociétés", "M&A"],
    },
    10: {
        "name_fr": "Restructuring / Entreprises en difficulté",
        "name_en": "Restructuring",
        "keywords_en": ["restructuring", "insolvency", "bankruptcy law"],
        "keywords_fr": ["restructuration", "entreprises en difficulté", "procédures collectives"],
    },
    11: {
        "name_fr": "Private Equity / Capital-Investissement",
        "name_en": "Private Equity",
        "keywords_en": ["private equity", "venture capital", "investment fund"],
        "keywords_fr": ["private equity", "capital-investissement", "fonds d'investissement"],
    },
    12: {
        "name_fr": "Droit Immobilier / Real Estate",
        "name_en": "Real Estate",
        "keywords_en": ["real estate law", "property law", "construction law"],
        "keywords_fr": ["droit immobilier", "droit de la construction"],
    },
    13: {
        "name_fr": "Financement de Projets",
        "name_en": "Project Finance",
        "keywords_en": ["project finance", "infrastructure finance", "PPP"],
        "keywords_fr": ["financement de projets", "project finance"],
    },
    14: {
        "name_fr": "Banque & Finance",
        "name_en": "Banking & Finance",
        "keywords_en": ["banking law", "financial regulation", "banking finance"],
        "keywords_fr": ["droit bancaire", "droit financier", "banque et finance"],
    },
    15: {
        "name_fr": "Droit Social",
        "name_en": "Employment & Labor Law",
        "keywords_en": ["employment law", "labor law", "HR legal"],
        "keywords_fr": ["droit social", "droit du travail"],
    },
    16: {
        "name_fr": "Droit Pénal",
        "name_en": "Criminal Law",
        "keywords_en": ["criminal law", "white collar crime", "criminal defense"],
        "keywords_fr": ["droit pénal", "droit pénal des affaires"],
    },
}

ROLES = {1: "Juriste", 2: "Avocat"}


def interactive_input() -> dict:
    """Collecte les critères de recherche via formulaire spécialisé."""
    print()
    print("=" * 60)
    print("   AGENT DE RECHERCHE DE CABINETS D'AVOCATS")
    print("=" * 60)
    print()

    # --- 1. Choix du rôle ---
    print("  Quel type de poste recherchez-vous ?")
    print("  1. Juriste")
    print("  2. Avocat")
    role_choice = input("  > ").strip()
    if role_choice not in ("1", "2"):
        print("\n  Erreur: Choisissez 1 ou 2.")
        sys.exit(1)
    role = ROLES[int(role_choice)]

    # --- 2. Choix de la spécialité ---
    print()
    print("  Quelle spécialité ?")
    print()
    # Affichage en 2 colonnes
    for i in range(1, 9):
        left = f"  {i:2d}. {SPECIALTIES[i]['name_fr']}"
        right = f"{i+8:2d}. {SPECIALTIES[i+8]['name_fr']}"
        print(f"  {left:<40s} {right}")
    print()
    spec_choice = input("  > ").strip()
    try:
        spec_num = int(spec_choice)
        if spec_num not in SPECIALTIES:
            raise ValueError
    except ValueError:
        print(f"\n  Erreur: Choisissez un numéro entre 1 et {len(SPECIALTIES)}.")
        sys.exit(1)
    specialty = SPECIALTIES[spec_num]

    # --- 3. Localisation ---
    print()
    location = input("  Quelle ville ?\n  > ").strip()
    if not location:
        print("\n  Erreur: La ville est obligatoire.")
        sys.exit(1)

    # --- 4. Nombre de cabinets ---
    print()
    count_str = input("  Combien de cabinets voulez-vous ? (défaut: 50)\n  > ").strip()
    try:
        count = int(count_str) if count_str else 50
    except ValueError:
        count = 50

    # --- 5. Précisions (optionnel) ---
    print()
    extra = input("  Précisions supplémentaires ? (Enter pour passer)\n  > ").strip()

    return {
        "role": role,
        "specialty": specialty,
        "specialty_num": spec_num,
        "location": location,
        "target_count": count,
        "extra": extra,
    }


def build_query(params: dict) -> str:
    """Construit la requête texte structurée."""
    spec = params["specialty"]
    parts = [
        f"Poste : {params['role']}",
        f"Spécialité : {spec['name_fr']} ({spec['name_en']})",
        f"Ville : {params['location']}",
    ]
    if params["extra"]:
        parts.append(f"Précisions : {params['extra']}")
    return "\n".join(parts)


def main():
    """Point d'entrée principal."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERREUR: ANTHROPIC_API_KEY manquante dans le .env")
        sys.exit(1)
    if not os.getenv("APOLLO_API_KEY"):
        print("ATTENTION: APOLLO_API_KEY manquante - l'outil Apollo ne fonctionnera pas")
    if not os.getenv("PERPLEXITY_API_KEY"):
        print("ATTENTION: PERPLEXITY_API_KEY manquante - l'outil web_search_legal ne fonctionnera pas")

    params = interactive_input()
    query = build_query(params)
    spec = params["specialty"]

    print()
    print("-" * 60)
    print("  RECAPITULATIF")
    print("-" * 60)
    print(f"  Poste       : {params['role']}")
    print(f"  Spécialité  : {spec['name_fr']} ({spec['name_en']})")
    print(f"  Ville       : {params['location']}")
    print(f"  Objectif    : {params['target_count']} cabinets")
    if params["extra"]:
        print(f"  Précisions  : {params['extra']}")
    print("-" * 60)
    print()

    confirm = input("  Lancer la recherche ? (O/n) > ").strip().lower()
    if confirm == "n":
        print("  Annulé.")
        sys.exit(0)

    print()
    print("=" * 60)
    print("   AGENT EN COURS D'EXECUTION")
    print("=" * 60)
    print()

    run_pipeline(
        user_query=query,
        target_count=params["target_count"],
        company_size="",
        specialty=params["specialty"],
    )


if __name__ == "__main__":
    main()
