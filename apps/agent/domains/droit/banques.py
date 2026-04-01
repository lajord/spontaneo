# ─── Ontologie metier ────────────────────────────────────────────────

ONTOLOGY = {
    "secteur": "Banque",
    "description": "Banques et etablissements financiers en France",
    "specialites": {
        "Banque de detail": {
            "metier": "Cette spécialité concerne les banques de détail et de proximité (réseaux d'agences), ciblant les particuliers et les professionnels locaux.",
        },
        "Banque privee": {
            "metier": "Cette spécialité cible la gestion de patrimoine et les services dédiés aux clients fortunés (wealth management).",
        },
        "Banque d'affaires / d'investissement": {
            "metier": "Cette spécialité couvre les grandes opérations financières (M&A, marchés de capitaux). Ce sont des entités prestigieuses, cibler les grandes banques et éviter de chercher via Google Maps.",
        },
        "Financement d'entreprises": {
            "metier": "Spécialité orientée sur le crédit et le financement au service des grandes entreprises et ETI (corporate lending).",
        },
        "Financement immobilier": {
            "metier": "Spécialité concernant les gros crédits immobiliers, hypothécaires et les financements de projets de promotion immobilière.",
        },
        "Financement de projets & infrastructures": {
            "metier": "Un pôle dédié au financement de grandes infrastructures (autoroutes, aéroports, énergies renouvelables) avec des montages complexes (PPP).",
        },
        "Trade Finance": {
            "metier": "Cette spécialité banque est surtout orientée pour les gens qui font du financement du commerce international (crédits documentaires, export). Ce sont surtout de grosses banques, donc éviter de chercher sur Google Maps.",
        },
        "Conformite & Reglementation bancaire": {
            "metier": "Un pôle axé sur la conformité (compliance), la lutte contre le blanchiment d'argent et le financement du terrorisme (LCB-FT), ainsi que la réglementation financière stricte.",
        },
    },
    "profils_et_contacts": {
        "Juriste Droit Bancaire": {
            "departement": "Juridique Credits / Financement",
            "contacts": [
                "Responsable Juridique Credits aux Particuliers / Professionnels (N+1)",
                "Responsable Juridique Financements Structures",
                "Head of Retail Banking Legal (N+2)",
                "Responsable de l'Ingenierie Patrimoniale",
                "Juriste Senior / Lead Lawyer sur un pole specifique (ex: Immobilier)",
            ],
            "instruction_ia": "L'IA doit utiliser cette section si le job title de la personne ciblée tourne autour du droit bancaire ou du crédit. Contacter les N+1 responsables de ces pôles de financement.",
        },
        "Juriste Financier": {
            "departement": "Marches de Capitaux / Investissement",
            "contacts": [
                "Head of Capital Markets Legal (Equity ou Debt - ECM/DCM)",
                "Responsable Juridique Derives et Produits Structures (ISDA/FBF)",
                "Head of Asset Management Legal",
                "Responsable Juridique Treasury & Liquidity",
                "General Counsel Global Markets (N+2)",
            ],
            "instruction_ia": "L'IA doit faire le rapprochement si le poste visé tourne autour des marchés financiers, dérivés ou asset management. Cibler les Head of Capital Markets ou General Counsel Global Markets.",
        },
        "Juriste Contentieux": {
            "departement": "Contentieux / Litigation",
            "contacts": [
                "Responsable Contentieux Affaires / Specialise",
                "Responsable Pre-contentieux et Recouvrement Amiable",
                "Head of Group Litigation (N+2 ou N+3)",
                "Responsable Juridique Risques et Assurances",
            ],
            "instruction_ia": "À utiliser si le poste du candidat concerne le contentieux, les litiges ou le recouvrement. Privilégier le responsable contentieux du pôle pertinent.",
        },
        "Juriste Compliance": {
            "departement": "Compliance / Securite Financiere",
            "contacts": [
                "Responsable LCB-FT (Lutte Contre le Blanchiment)",
                "Responsable Securite Financiere / Sanctions et Embargos",
                "Deontologue (Ethics Officer)",
                "Data Protection Officer (DPO)",
                "Responsable Conformite des Services d'Investissement (RCSI)",
                "Chief Compliance Officer (CCO) (N+2)",
            ],
            "instruction_ia": "L'IA doit s'en servir si le job title de la personne est axé 'Compliance' ou 'Conformité'. Contacter le CCO ou responsables spécifiques à la lutte antiblanchiment.",
        },
        "Juriste Corporate / M&A": {
            "departement": "Corporate / Gouvernance",
            "contacts": [
                "Responsable Droit des Societes / Gouvernance",
                "Head of Corporate Legal",
                "Responsable Juridique M&A / Participations",
                "Secretaire General",
                "Responsable du Secretariat du Conseil d'Administration",
            ],
            "instruction_ia": "Utiliser cette section si le poste visé est axé Droit des sociétés, Corporate M&A ou Secrétariat Général.",
        },
        "Contacts RH (complement)": {
            "departement": "Ressources Humaines",
            "contacts": [
                "Talent Acquisition Manager - Legal & Compliance",
                "HR Business Partner (HRBP) Fonctions Support",
                "Charge de recrutement BFI",
            ],
            "instruction_ia": "Option de secours : Si aucun opérationnel N+1 n'est trouvé, rediriger vers ces fonctions de recrutement en charge du juridique et de la conformité.",
        },
    },
    "recherche_apollo": {
        "seniorities": ["director", "vp", "c_suite", "owner"],
        "technique_perplexity": "(Responsable OR Head OR Manager) AND (Juridique OR Legal) AND [specialite] AND [Nom de la banque]",
    },
}
