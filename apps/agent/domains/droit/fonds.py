from domains.base import VerticalConfig, Subspecialty


# ─── Sous-specialites des fonds d'investissement ────────────────────

SUBSPECIALTIES = {
    1: Subspecialty(id=1, name="Private Equity / Capital-investissement"),
    2: Subspecialty(id=2, name="Venture Capital / Capital-risque"),
    3: Subspecialty(id=3, name="Dette privee"),
    4: Subspecialty(id=4, name="Immobilier"),
    5: Subspecialty(id=5, name="Infrastructure"),
    6: Subspecialty(id=6, name="Fonds de fonds"),
    7: Subspecialty(id=7, name="Impact / ESG"),
    8: Subspecialty(id=8, name="Situations speciales / Distressed"),
}


# ─── Configuration verticale ────────────────────────────────────────

FONDS = VerticalConfig(
    id="fonds",
    domain="droit",
    label_fr="Fonds d'investissement",

    collect_prompt="""\
Tu es un agent expert en intelligence économique et recrutement spécialisé dans le secteur des Fonds d’investissements.
Objectif : Identifier tous les fonds d'investissement (Capital Innovation, Développement, Transmission et Family Offices, Venture Capital) ayant un bureau dans la zone ciblée et identifier de potentielles cibles pour la direction juridique.

Instructions de recherche (Identification des Fonds) :
Utilise des requêtes de recherche web pour lister les sociétés de gestion et fonds présents dans la zone cible. 
Appuie-toi sur des sources comme : les annuaires de places financières locales (ex: Lyon Place Financière), les sites spécialisés (CFNEWS, Private Equity Magazine, Finkey) et LinkedIn.

## OUTILS A TA DISPOSITION

Tu peux utiliser intelligemment les outils suivants pour itérer sur la recherche :

1. **web_search_legal** — TRÈS IMPORTANT pour itérer sur la recherche. Utilise-le massivement pour fouiller les annuaires locaux, CFNEWS, Finkey, etc.
2. **apollo_search** — Fais des appels SÉPARÉS :
   - Un appel avec **keywords** EN ANGLAIS (ex: "private equity", "venture capital", "asset management")
   - Un appel avec **job_titles** EN ANGLAIS (ex: "Investment Director", "Partner", "Legal Counsel", "General Counsel")

ATTENTION : Il est STRICTEMENT INTERDIT d'utiliser l'outil `google_maps_search` (ou apify google maps). Ne l'utilise sous aucun prétexte.


## REGLES SPECIFIQUES
- Pousse la recherche web autant que nécessaire pour bien explorer les annuaires.
- Ne mélange JAMAIS keywords et job_titles dans un même appel Apollo.
""",

    enrich_prompt="""\
Tu enrichis un fonds d'investissement.

## CONTACTS A CIBLER

Pour chaque fonds, trouve les profils suivants :
- Directeur Juridique / Responsable Juridique / General Counsel
- Associe / Managing Partner (2 max — choisis les plus pertinents, sinon prends au hasard)
- Juriste Private Equity
- Juriste Corporate M&A / Transactionnel
- Juriste Structuration de Fonds

Si tu ne trouves pas certains profils specifiques, ce n'est pas grave — prends les decideurs
les plus proches (partner, directeur) et passe au fonds suivant.

## PAGES A CRAWLER EN PRIORITE
1. Page d'accueil — comprendre la structure du fonds
2. Page equipe / team (/team, /equipe, /our-team, /people) — LA PLUS IMPORTANTE
3. Page contact (/contact)
4. Mentions legales (/mentions-legales)

## STRATEGIE SPECIFIQUE AUX FONDS
- Les fonds ont souvent des sites minimalistes avec une page "Team" bien remplie.
  Crawle cette page en priorite pour extraire les noms et titres.
- Utilise apollo_people_search en mode RECHERCHE avec le domaine
  + person_seniorities=["owner", "partner", "c_suite", "director"]
- Pour chaque nom trouve sans email : apollo_people_search en mode MATCH
- Perplexity est utile pour trouver les profils LinkedIn des partners
  ("partners [Nom du fonds] LinkedIn", "[Nom] investment director [Fonds]")
- Verifie chaque email avec neverbounce_verify.
- Ne garde PAS les emails generiques (contact@, info@).
""",

    subspecialties=SUBSPECIALTIES,
    ignore_subspecialty_in_collect=True,
)
