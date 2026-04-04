# ─── Ontologie metier ────────────────────────────────────────────────

ONTOLOGY = {
    "secteur": "Fond d'investissement",
    "description": "Fonds d'investissement, societes de gestion et family offices en France",
    "specialites": {
        "Private Equity / Capital-investissement": {
            "metier": "Concerne l'investissement au capital de sociétés non cotées (LBO, capital-développement). Ce sont souvent des fonds structurés, ne pas chercher via Google Maps.",
        },
        "Venture Capital / Capital-risque": {
            "metier": "Axé sur le financement de startups et sociétés innovantes lors de leurs levées de fonds (Seed, Serie A, etc.).",
        },
        "Dette privee": {
            "metier": "Spécialité autour des fonds prêtant directement aux entreprises (financement mezzanine, direct lending).",
        },
        "Immobilier": {
            "metier": "Fonds gérant des actifs immobiliers (SCPI, OPCI) pour créer du rendement locatif ou de la plus-value de cession.",
        },
        "Infrastructure": {
            "metier": "Fonds investissant dans l'énergie, les autoroutes, la santé, etc. Très gros tickets d'investissement.",
        },
        "Fonds de fonds": {
            "metier": "Structure qui investit dans d'autres fonds d'investissement plutôt que directement dans des entreprises.",
        },
        "Impact / ESG": {
            "metier": "Fonds dont la thèse d'investissement est centrée sur l'environnement, le social ou la gouvernance (ESG).",
        },
        "Situations speciales / Distressed": {
            "metier": "Spécialité très technique qui consiste à racheter des entreprises en grande difficulté financière (dette distressed).",
        },
    },
    "profils_et_contacts": {
        "Directeur Juridique / General Counsel": {
            "departement": "Direction Juridique",
            "contacts": [
                "Directeur Juridique / Responsable Juridique",
                "General Counsel",
            ],
            "instruction_ia": "L'IA doit faire le lien ici si le job title de la personne ciblée est 'Juriste' ou 'Legal Counsel' généraliste au sein du fonds. Le contact à cibler est le General Counsel directement.",
        },
        "Associe / Managing Partner": {
            "departement": "Direction / Investissement",
            "contacts": [
                "Associe / Partner (2 max, les plus pertinents)",
                "Managing Partner",
            ],
            "instruction_ia": "Typiquement pour des petites structures (boutiques) ou si le candidat vise un poste très senior / d'investissement, s'adresser aux Partners qui gèrent le deal flow.",
        },
        "Juriste Private Equity": {
            "departement": "Juridique Transactionnel",
            "contacts": [
                "Juriste Private Equity",
                "Juriste Corporate M&A / Transactionnel",
                "Juriste Structuration de Fonds",
            ],
            "instruction_ia": "L'IA doit utiliser cette section si le poste visé est 'Juriste M&A' ou 'Private Equity' pour s'adresser aux équipes en charge des transactions au sein du fonds.",
        },
    },
    "sources_recherche": [
        "Annuaires de places financieres locales (ex: Lyon Place Financiere)",
        "CFNEWS",
        "Private Equity Magazine",
        "Finkey",
        "LinkedIn",
    ],

}
