# ─── Ontologie metier ────────────────────────────────────────────────


ONTOLOGY = {
    "scope_stricte": "Uniquement les Cabinets d'Avocats en France. ",
    "secteur": "Cabinet Avocat",
    "description": "Cartographie des départements en cabinets d'avocats d'affaires en France",


"specialites": {
        "Contentieux des Affaires": {
            "metier": "Conseil juridique en litiges commerciaux, conflits d'actionnaires et procédures devant les tribunaux de commerce.",
            "categorie": "Contentieux / Litigation",
        },
        "Arbitrage": {
            "metier": "Conseil juridique en résolution de litiges internationaux complexes hors tribunaux étatiques (justice privée internationale).",
            "categorie": "Contentieux / Arbitration",
        },
        "Concurrence / Antitrust": {
            "metier": "Conseil juridique en droit de la concurrence, contrôle des concentrations, cartels et aides d'État.",
            "categorie": "Droit Économique",
        },
        "Distribution & Consommation": {
            "metier": "Conseil juridique en contrats de franchise, réseaux de distribution, droit de la consommation et réglementations commerciales.",
            "categorie": "Droit Commercial",
        },
        "IP / IT": {
            "metier": "Conseil juridique en propriété intellectuelle (marques, brevets) et droit des technologies (IT, logiciels, RGPD).",
            "categorie": "Innovation & Technologies",
        },
        "Droit Fiscal": {
            "metier": "Conseil juridique en fiscalité des entreprises (M&A), fiscalité patrimoniale, intégration fiscale et contentieux fiscal.",
            "categorie": "Fiscalité",
        },
        "Droit Boursier": {
            "metier": "Conseil juridique en marchés de capitaux, introductions en bourse (IPO) et réglementation de l’AMF.",
            "categorie": "Finance / Marchés",
        },
        "Debt Finance": {
            "metier": "Conseil juridique en financements structurés, crédits syndiqués et gestion de la dette (senior, mezzanine).",
            "categorie": "Finance / Crédits",
        },
        "Corporate M&A": {
            "metier": "Conseil juridique en fusions-acquisitions, cessions, private equity et droit général des sociétés.",
            "categorie": "Corporate / Droit des Sociétés",
        },
        "Restructuring": {
            "metier": "Conseil juridique pour entreprises en difficulté : mandat ad hoc, conciliation et procédures de sauvegarde ou redressement.",
            "categorie": "Corporate / Droit des Entreprises en Difficulté",
        },
        "Private Equity": {
            "metier": "Conseil juridique en opérations de haut de bilan pour fonds d’investissement (LBO, Venture Capital).",
            "categorie": "Corporate / Haut de Bilan",
        },
        "Droit Immobilier": {
            "metier": "Conseil juridique en transactions immobilières, baux commerciaux, droit de la construction et urbanisme.",
            "categorie": "Immobilier / Construction",
        },
        "Financement de Projets": {
            "metier": "Conseil juridique en financement d’infrastructures majeures (énergie, transport, partenariats public-privé).",
            "categorie": "Finance / Projets & Infrastructures",
        },
        "Banque & Finance": {
            "metier": "Conseil juridique en réglementation bancaire, conformité (ACPR) et conseil aux institutions financières.",
            "categorie": "Finance / Banque",
        },
        "Droit Social": {
            "metier": "Conseil juridique en droit du travail (individuel et collectif), restructurations RH et relations syndicales.",
            "categorie": "Social / Ressources Humaines",
        },
        "Droit Pénal des Affaires": {
            "metier": "Conseil juridique en droit pénal des affaires : corruption, abus de biens sociaux, fraude fiscale et blanchiment.",
            "categorie": "Pénal / Conformité",
        },
    },
"profils_et_contacts": {
        "Avocat Collaborateur / Counsel": {
            "departement": "Equipe Juridique (Par domaine de competence)",
            "contacts": [
                "Associe Fondateur (Founder / Managing Partner) - si petit cabinet",
                "Associe (Partner) specialise dans le domaine d'expertise du candidat",
                "Counsel (N+1 direct dans l'equipe)",
            ],
            "instruction_ia": "L'IA doit utiliser cette section si le candidat est lui-même Avocat. Faire correspondre la spécialité du candidat avec l'associé du cabinet en charge de cette pratique.",
        },
        "Fonction Support (RH, Marketing)": {
            "departement": "Fonctions Support / Secrétariat Général",
            "contacts": [
                "Office Manager (pour les petites structures)",
                "DRH / Responsable Recrutement",
                "Secretaire General (pour les très grands cabinets Anglo-Saxons)",
            ],
            "instruction_ia": "Utiliser cette section si le candidat cible un poste non-juridique (marketing, assistanat, RH) dans un cabinet d'avocat.",
        },
    },
    "email_patterns": [
        "prenom.nom@cabinet.fr",
        "p.nom@cabinet.fr",
        "initiale.nom@cabinet.fr",
        "nom@cabinet.fr",
	 "nom.prenom@cabinet.fr",
    ],
}
