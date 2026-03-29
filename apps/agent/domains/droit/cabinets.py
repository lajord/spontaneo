from domains.base import VerticalConfig, Subspecialty


# ─── Sous-specialites des cabinets d'avocats ────────────────────────

SUBSPECIALTIES = {
    1: Subspecialty(id=1, name="Contentieux des Affaires"),
    2: Subspecialty(id=2, name="Arbitrage"),
    3: Subspecialty(id=3, name="Concurrence / Antitrust"),
    4: Subspecialty(id=4, name="Distribution & Consommation"),
    5: Subspecialty(id=5, name="IP / IT"),
    6: Subspecialty(id=6, name="Droit Fiscal"),
    7: Subspecialty(id=7, name="Droit Boursier"),
    8: Subspecialty(id=8, name="Debt Finance"),
    9: Subspecialty(id=9, name="Corporate M&A / Fusions-Acquisitions"),
    10: Subspecialty(id=10, name="Restructuring / Entreprises en difficulte"),
    11: Subspecialty(id=11, name="Private Equity / Capital-Investissement"),
    12: Subspecialty(id=12, name="Droit Immobilier / Real Estate"),
    13: Subspecialty(id=13, name="Financement de Projets"),
    14: Subspecialty(id=14, name="Banque & Finance"),
    15: Subspecialty(id=15, name="Droit Social"),
    16: Subspecialty(id=16, name="Droit Penal"),
}


# ─── Configuration verticale ────────────────────────────────────────

CABINETS = VerticalConfig(
    id="cabinets",
    domain="droit",
    label_fr="Cabinets d'avocats",

    collect_prompt="""\
Tu cherches des cabinets d'avocats specialises dans le domaine demande, dans la ville demandee.

## OUTILS A TA DISPOSITION

Choisis les outils de recherche de manière intelligente selon la situation (pas la peine de tous les utiliser systématiquement si ce n'est pas pertinent) :

1. **apollo_search** — TOUJOURS faire 2 appels SEPARES :
   - Un appel avec **keywords** EN ANGLAIS (tags secteur/activite, ex: "labor law", "employment law")
   - Un appel avec **job_titles** EN ANGLAIS (titres de poste, ex: "Labor Law Attorney", "Employment Lawyer")
   NE JAMAIS combiner keywords et job_titles dans le meme appel.
   Varie les termes a chaque iteration.
2. **web_search_legal** — requete EN FRANCAIS
   Varie les formulations (ex: "cabinet avocat droit social", "avocats specialises droit du travail").
   Sources a explorer : annuaires du barreau, Pages Jaunes, avocats.fr, Legal 500, Chambers, Decideurs.
3. **google_maps_search** — keywords EN FRANCAIS
   Efficace pour les petits cabinets locaux (ex: ["avocat droit social Pau"]).

## REGLES SPECIFIQUES
- Apollo = 2 appels separes : un avec keywords EN ANGLAIS, un avec job_titles EN ANGLAIS. JAMAIS les deux ensemble.
- Web search et Google Maps = tout EN FRANCAIS.
""",

    verify_prompt="""\
VERIFICATION OBLIGATOIRE avant enrichissement.
Apres le crawl de la homepage, verifie que ce cabinet pratique bien la specialite : **{subspecialty}**

METHODE :
- Analyse le contenu de la homepage et identifie les pages de competences
  (/competences, /expertises, /domaines, /practices, /savoir-faire, /activites)
- Si la homepage ne suffit pas, crawle UNE page de competences pour confirmer.
- La specialite peut apparaitre sous des termes proches ou en anglais
  (ex: "Arbitrage" = "arbitrage international", "resolution des differends", "dispute resolution")

DECISION :
- PERTINENT : la specialite est mentionnee dans les domaines du cabinet → continue l'enrichissement normalement.
- NON PERTINENT : aucune mention de la specialite ou specialite totalement differente
  → appelle save_enrichment avec une liste VIDE et arrete immediatement (ne perds pas de temps).
""",

    enrich_prompt="""\
Tu enrichis un cabinet d'avocats. Les decideurs a cibler sont :
- Les associes (partners) — cibles PRIORITAIRES
- Le managing partner / gerant
- Le directeur general / directeur administratif
- Le responsable RH / recrutement (si le cabinet est assez grand)

## PAGES A CRAWLER EN PRIORITE
1. Page d'accueil — comprendre la structure du cabinet
2. Page equipe / associes / partners (/equipe, /team, /avocats, /lawyers, /associes, /partners)
3. Page contact (/contact, /nous-contacter)
4. Mentions legales (/mentions-legales, /legal) — contient souvent des emails

## PATTERNS D'EMAILS COURANTS DANS LES CABINETS
- prenom.nom@cabinet.fr
- p.nom@cabinet.fr
- initiale.nom@cabinet.fr
- nom@cabinet.fr

## STRATEGIE
1. Crawle d'abord le site pour trouver les noms des associes sur la page equipe
2. Si tu trouves un nom mais pas son email : utilise apollo_people_search en mode MATCH (prenom + nom + domaine)
3. Si Apollo ne trouve rien : cherche sur Perplexity "email [Nom] avocat [Cabinet] [Ville]"
4. Verifie chaque email trouve avec neverbounce_verify
5. Ne garde PAS les emails generiques (contact@, info@, accueil@) — on veut les decideurs
""",

    subspecialties=SUBSPECIALTIES,
)
