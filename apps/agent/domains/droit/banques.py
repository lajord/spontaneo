from domains.base import VerticalConfig, Subspecialty


# ─── Sous-specialites bancaires ─────────────────────────────────────

SUBSPECIALTIES = {
    1: Subspecialty(id=1, name="Banque de detail"),
    2: Subspecialty(id=2, name="Banque privee"),
    3: Subspecialty(id=3, name="Banque d'affaires / d'investissement"),
    4: Subspecialty(id=4, name="Financement d'entreprises"),
    5: Subspecialty(id=5, name="Financement immobilier"),
    6: Subspecialty(id=6, name="Financement de projets & infrastructures"),
    7: Subspecialty(id=7, name="Trade Finance"),
    8: Subspecialty(id=8, name="Conformite & Reglementation bancaire"),
}


# ─── Configuration verticale ────────────────────────────────────────

BANQUES = VerticalConfig(
    id="banques",
    domain="droit",
    label_fr="Banques & etablissements financiers",

    collect_prompt="""\
Tu es un agent expert en business intelligence spécialisé dans le secteur bancaire et financier.
Objectif : Cartographier exhaustivement les institutions financières (banques, sociétés de gestion, crédits) présentes dans la zone cible.
Ton objectif global est de trouver TOUS les types de banques, de manière mélangée. Varie les mots clés pour trouver 5 banques de détail, puis 5 banques d'affaires, puis 5 banques privées, etc.

## OUTILS A TA DISPOSITION

Tu DOIS utiliser uniquement :
1. **apollo_search** — Fais des appels SÉPARÉS et varie tes mots-clés :
   - Un appel avec **keywords** EN ANGLAIS (ex: "retail bank", "investment banking", "private banking", "wealth management", "trade finance")
   - Un appel avec **job_titles** EN ANGLAIS (ex: "Banking Director", "Credit Analyst", "Partner")
2. **web_search_legal** — Requête EN FRANÇAIS pour fouiller des annuaires, classements Agefi, Les Echos, etc.

ATTENTION : Il est STRICTEMENT INTERDIT d'utiliser l'outil `google_maps_search` (ou apify google maps). Ne l'utilise sous aucun prétexte.
""",

    enrich_prompt="""\
Tu enrichis une banque ou un etablissement financier.

## CONTACTS A CIBLER SELON LE PROFIL

Si un PROFIL CIBLE est indique ci-dessus, utilise le mapping ci-dessous pour cibler les bons contacts.
Sinon, cible les decideurs generaux (DG, directeurs, managing directors).

### Juriste Droit Bancaire (Banque de Detail / Financement)
- Responsable Juridique Credits aux Particuliers / Professionnels (N+1)
- Responsable Juridique Financements Structures
- Head of Retail Banking Legal (N+2)
- Responsable de l'Ingenierie Patrimoniale
- Juriste Senior / Lead Lawyer sur un pole specifique (ex: Immobilier)

### Juriste Financier (Marches de Capitaux / Investissement)
- Head of Capital Markets Legal (Equity ou Debt - ECM/DCM)
- Responsable Juridique Derives et Produits Structures (ISDA/FBF)
- Head of Asset Management Legal
- Responsable Juridique Treasury & Liquidity
- General Counsel Global Markets (N+2)

### Juriste Contentieux (Litigation)
- Responsable Contentieux Affaires / Specialise
- Responsable Pre-contentieux et Recouvrement Amiable
- Head of Group Litigation (N+2 ou N+3)
- Responsable Juridique Risques et Assurances

### Juriste Compliance (Conformite / Securite Financiere)
- Responsable LCB-FT (Lutte Contre le Blanchiment)
- Responsable Securite Financiere / Sanctions et Embargos
- Deontologue (Ethics Officer)
- Data Protection Officer (DPO)
- Responsable Conformite des Services d'Investissement (RCSI)
- Chief Compliance Officer (CCO) (N+2)

### Juriste Corporate / M&A
- Responsable Droit des Societes / Gouvernance
- Head of Corporate Legal
- Responsable Juridique M&A / Participations
- Secretaire General
- Responsable du Secretariat du Conseil d'Administration

### Contacts RH Specialises (toujours utiles en complement)
- Talent Acquisition Manager - Legal & Compliance
- HR Business Partner (HRBP) Fonctions Support
- Charge de recrutement BFI

## PAGES A CRAWLER EN PRIORITE
1. Page d'accueil — comprendre la structure
2. Page direction / gouvernance / comite executif (/gouvernance, /direction, /leadership, /about-us)
3. Page contact (/contact)
4. Page equipe / nos experts (/equipe, /team)
5. Mentions legales (/mentions-legales)

## STRATEGIE SPECIFIQUE AUX BANQUES
- Les grandes banques ont souvent des sites corporate avec peu de contacts directs.
  Utilise apollo_people_search en mode RECHERCHE avec le domaine + person_seniorities=["director", "vp", "c_suite"]
- Pour les boutiques M&A, la page "equipe" contient souvent les noms des partners.
  Crawle cette page puis utilise Apollo en mode MATCH pour chaque nom.
- Perplexity est utile pour trouver les noms des dirigeants sur LinkedIn, Les Echos, Agefi.
- Verifie chaque email avec neverbounce_verify.
- Ne garde PAS les emails generiques (contact@, info@).

## TECHNIQUE DE RECHERCHE LINKEDIN/APOLLO
Pour trouver les bons intitules, utilise ces patterns dans apollo_people_search :
- person_titles: les intitules EN ANGLAIS et EN FRANCAIS du profil cible
- person_seniorities: ["director", "vp", "c_suite", "owner"]
Pour Perplexity, utilise la recherche booleenne :
  (Responsable OR Head OR Manager) AND (Juridique OR Legal) AND [specialite] AND "[Nom de la banque]"
Si la banque est etrangere (JP Morgan, Morgan Stanley, Lazard), les titres seront EN ANGLAIS.
""",

    subspecialties=SUBSPECIALTIES,
    ignore_subspecialty_in_collect=True,
)
