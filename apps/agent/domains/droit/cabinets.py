# ─── Ontologie metier ────────────────────────────────────────────────

ONTOLOGY = {
    "secteur": "Cabinet Avocat",
    "description": "Cabinets d'avocats d'affaires en France",
    "specialites": {
        "Contentieux des Affaires": {
            "metier": "Cabinets intervenant sur les litiges commerciaux et conflits d'actionnaires. Concerne les avocats qui plaident aux tribunaux de commerce.",
        },
        "Arbitrage": {
            "metier": "Concerne la résolution de litiges internationaux complexes hors tribunaux (arbitrage international). Souvent au sein de très prestigieux cabinets.",
        },
        "Concurrence / Antitrust": {
            "metier": "Axé sur le droit de la concurrence, les aides d'Etat et le contrôle des concentrations (M&A antitrust).",
        },
        "Distribution & Consommation": {
            "metier": "Concerne les contrats de franchise, droit de la consommation et réglementations de distribution des grandes enseignes.",
        },
        "IP / IT": {
            "metier": "Spécialité couvrant la propriété intellectuelle (brevets, marques) et le droit du numérique / des technologies (IT, RGPD).",
        },
        "Droit Fiscal": {
            "metier": "Concerne l'ingénierie fiscale, la gestion de patrimoine, et les impôts sur le revenu ou les sociétés.",
        },
        "Droit Boursier": {
            "metier": "Cible le droit des marchés de capitaux, les introductions en bourse et la réglementation AMF. Cabinets très spécifiques sur la place parisienne.",
        },
        "Debt Finance": {
            "metier": "Pratique du financement structuré et des grands crédits syndiqués.",
        },
        "Corporate M&A": {
            "metier": "La pratique centrale des cabinets d'affaires : fusions & acquisitions, droit des sociétés, private equity.",
        },
        "Restructuring": {
            "metier": "Concerne le traitement de la restructuration d'entreprises en difficulté financière (procédures collectives).",
        },
        "Private Equity": {
            "metier": "Cabinets accompagnant les fonds d'investissement (LBO, venture capital).",
        },
        "Droit Immobilier": {
            "metier": "Avocats intervenant en droit de la construction, urbanisme, et grandes transactions immobilières.",
        },
        "Financement de Projets": {
            "metier": "Soutien juridique aux grands financements d'infrastructures (autoroutes, éolien, minier).",
        },
        "Banque & Finance": {
            "metier": "Cabinets ayant une réglementation bancaire ou conseillant les établissements de crédit.",
        },
        "Droit Social": {
            "metier": "Droit du travail, restructurations RH, et relations avec les syndicats.",
        },
        "Droit Penal": {
            "metier": "Droit pénal des affaires, défense lors de fraudes fiscales, délits d'initiés, corruption.",
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
    ],
}
