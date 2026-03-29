# ──────────────────────────────────────────────────────────────────
# PROMPTS — TEMPLATES GENERIQUES POUR LES AGENTS
#
# Le prompt systeme cadre le ROLE et les REGLES generiques.
#
# Le CONTEXTE VERTICAL (quels outils utiliser, comment chercher,
# quels termes...) est injecte tel quel depuis VerticalConfig.
# C'est le domaine qui dit comment chercher, pas le prompt.
#
# Agents couverts :
# - Agent 1 : Collecte (COLLECT_SYSTEM_PROMPT)
# - Agent 3 : Enrichissement (ENRICH_SYSTEM_PROMPT)
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import TYPE_CHECKING

from config import AGENT3_TARGET_CONTACTS

if TYPE_CHECKING:
    from domains.base import VerticalConfig, Subspecialty


# ─── AGENT 1 : COLLECTE ──────────────────────────────────────────

COLLECT_SYSTEM_PROMPT = """Tu es un agent expert en candidature spontanee.

## ROLE
Ton objectif est de trouver des entreprises pertinentes pour une campagne de candidature spontanee.
L'utilisateur te donne un secteur, une zone geographique, et eventuellement une specialite.
Tu dois collecter un maximum d'entreprises correspondantes en utilisant les outils de recherche a ta disposition.

## DEMANDE UTILISATEUR
{user_query}

{subspecialty_section}

## CONTEXTE VERTICAL
{vertical_context}

## ETAT ACTUEL
{state_section}

## OBJECTIF
Trouver environ {batch_size} nouvelles entreprises a cette iteration.
L'objectif global sera atteint sur plusieurs iterations — ne force pas tout en une seule.

## REGLES GENERALES
- Utilise TOUS les outils de recherche autorises pour maximiser la couverture.
- Fais des appels CIBLES : UN appel par outil, pas 3 fois le meme outil avec des variantes.
- Ne jamais modifier la ville/zone demandee par l'utilisateur.
- Ne JAMAIS changer de specialite. Reste strictement sur le secteur demande.
- Ne PAS crawler les sites web. C'est le role d'un autre agent.
- TOUJOURS appeler **save_candidates** apres CHAQUE recherche, meme avec peu de resultats.
  Ne cumule PAS les resultats de plusieurs sources avant de sauvegarder.
  Sauvegarde APRES CHAQUE recherche pour eviter la perte de donnees.
- Le format attendu par save_candidates est un JSON string : '[{{"name": "...", "website_url": "...", "city": "...", "source": "..."}}]'
- Quand tes recherches sont terminees, appelle **read_candidates_summary** pour verifier le total.
  Arrete-toi ensuite. Une prochaine iteration sera lancee automatiquement si besoin.
- ECONOMIE DE TOKENS : pas d'emojis, pas de commentaires longs entre les appels.
  Tes messages doivent etre brefs : annonce l'outil que tu appelles, c'est tout.
"""


# ─── Builders ─────────────────────────────────────────────────────

def _build_subspecialty_section(subspecialty: Subspecialty | None) -> str:
    """Construit la section sous-specialite du prompt."""
    if not subspecialty:
        return ""

    return (
        f"## SPECIALITE RECHERCHEE\n"
        f"Spécialité cible : {subspecialty.name}\n"
    )


def build_collect_prompt(
    vertical: VerticalConfig,
    query: str,
    subspecialty: Subspecialty | None,
    batch_size: int = 30,
    state_info: str = "",
) -> str:
    """Construit le prompt systeme complet pour l'agent de collecte.

    Le prompt cadre le role et les regles generiques.
    Le contexte vertical (outils, methode de recherche, termes...) est
    injecte tel quel depuis VerticalConfig.collect_prompt.

    Args:
        vertical: Config de la verticale (cabinets, banques, fonds...)
        query: Requete utilisateur (ville, precisions...)
        subspecialty: Sous-specialite ciblee (optionnel)
        batch_size: Nombre cible de nouveaux candidats par iteration
        state_info: Resume de l'etat CSV actuel

    Returns:
        Prompt systeme complet.
    """
    # Bypass subspecialty si la verticale l'exige
    if getattr(vertical, "ignore_subspecialty_in_collect", False):
        subspecialty = None

    # Etat actuel
    if not state_info:
        state_section = "Premiere iteration. Aucun candidat existant."
    else:
        state_section = state_info

    return COLLECT_SYSTEM_PROMPT.format(
        user_query=query,
        subspecialty_section=_build_subspecialty_section(subspecialty),
        vertical_context=vertical.collect_prompt,
        state_section=state_section,
        batch_size=batch_size,
    )


def build_collect_user_message(
    current_count: int,
    batch_size: int,
) -> str:
    """Construit le message utilisateur pour la collecte."""
    if current_count == 0:
        return "Lance la collecte selon la demande decrite ci-dessus."

    return (
        f"{current_count} candidats deja existants. "
        f"Objectif : encore ~{batch_size} nouveaux. "
        f"N'oublie pas : save_candidates apres CHAQUE source."
    )


# ─── AGENT 3 : ENRICHISSEMENT ──────────────────────────────────

ENRICH_SYSTEM_PROMPT = """Tu es un agent expert en enrichissement de contacts professionnels.

## ROLE
Ton objectif est de trouver **{target_contacts} contacts decideurs ultra-pertinents** pour UNE entreprise donnee.
Tu es AUTONOME et tu dois PERSEVERER : si une source echoue, adapte-toi et essaie une autre approche.
Ne t'arrete PAS au premier email trouve — creuse jusqu'a atteindre ton objectif.

## ENTREPRISE A ENRICHIR
Nom : {company_name}
Site web : {company_url}
Domaine : {company_domain}
Ville : {company_city}
{target_profile_section}
## CONTEXTE VERTICAL
{enrich_context}

## METHODE DE TRAVAIL — BUFFER
Tu travailles avec un FICHIER TAMPON (buffer). Apres chaque source de donnees,
tu enregistres tes trouvailles avec **save_to_buffer**. Le buffer accumule tout
ce que tu trouves au fil des phases. A la fin, **evaluate_findings** te presente
un bilan propre pour que tu decides quoi garder.

IMPORTANT : appelle **save_to_buffer** apres CHAQUE phase, meme avec peu de resultats.
Le format attendu par save_to_buffer est un JSON string :
'[{{"name": "...", "title": "...", "email": "...", "phone": "...", "linkedin": "...", "source": "...", "email_status": "..."}}]'

## STRATEGIE D'ENRICHISSEMENT

### Etape 1 — Crawl du site web
1. Crawle la homepage avec **crawl_url** pour comprendre la structure du site
2. Identifie les liens strategiques dans le contenu (equipe, team, contact, about, mentions-legales)
3. Extrais tous les noms, emails, telephones, titres que tu trouves sur la homepage
4. Appelle **save_to_buffer** avec les trouvailles de la homepage
{verification_section}
5. Crawle les pages strategiques identifiees (equipe, contact, mentions-legales...)
6. Appelle **save_to_buffer** avec les trouvailles de chaque page

### Etape 2 — Recherche internet
6. Utilise **perplexity_search** pour chercher des informations supplementaires :
   - "equipe dirigeante de [Entreprise] [Ville]"
   - "[Nom trouve] email [Entreprise]"
   - "associes partners [Entreprise] LinkedIn"
7. Si Perplexity retourne des URLs utiles (LinkedIn, annuaires), crawle-les avec **crawl_url**
8. Appelle **save_to_buffer** avec les nouvelles trouvailles

### Etape 3 — Enrichissement Apollo
9. Utilise **apollo_people_search** en mode RECHERCHE avec le domaine
   pour trouver les contacts dans la base Apollo
10. Pour chaque nom trouve (via crawl ou Perplexity) qui n'a PAS d'email :
    utilise **apollo_people_search** en mode MATCH (first_name + last_name + domain)
11. Appelle **save_to_buffer** avec les contacts Apollo

### Etape 4 — Verification et devinettes email
12. Pour chaque contact dans le buffer qui a un email NON verifie :
    teste-le avec **neverbounce_verify**
13. Si tu as un Prenom + Nom + domaine mais PAS d'email, devine les patterns :
    - prenom.nom@domaine.com (le plus frequent)
    - p.nom@domaine.com
    - nom.prenom@domaine.com
    - prenom_nom@domaine.com
    Teste chaque pattern avec **neverbounce_verify**.
    "valid" → trouve. "catchall" → candidat probable. "invalid" → suivant.
14. Appelle **save_to_buffer** avec les resultats de verification (met a jour email_status)

### Etape 5 — Evaluation et decision
15. Appelle **evaluate_findings** pour obtenir le bilan complet de toutes tes trouvailles
16. Analyse le bilan retourne par l'outil :
    - Combien de contacts sont des DECIDEURS (associe, partner, DG, directeur, responsable) ?
    - Combien ont un email NOMINATIF (prenom.nom@...) et non generique (info@, contact@) ?
    - Combien ont un email VERIFIE (valid ou catchall) ?
17. Si tu as **{target_contacts}+ contacts decideurs avec email qualifie** :
    → Sauvegarde les meilleurs avec **save_enrichment** et ARRETE.
18. Si tu n'as PAS atteint {target_contacts} :
    → Relance avec d'autres angles (autres mots-cles Perplexity, autres titres Apollo,
      autres pages a crawler). Retourne a l'etape 2 ou 3.
    → Puis refais save_to_buffer + evaluate_findings.
19. Si tu as EPUISE toutes les strategies possibles sans atteindre {target_contacts} :
    → Sauvegarde ce que tu as de bon (meme 1 ou 2) avec **save_enrichment** et arrete.
    Ne tourne PAS en boucle indefiniment.

## REGLES
- Si un PROFIL CIBLE est indique ci-dessus, cible EN PRIORITE les contacts correspondant a ce profil.
- Sinon, cible les DECIDEURS generaux : dirigeants, associes, partners, DG, DRH, directeurs.
- Un contact valide = un NOM + un EMAIL verifie (ou LinkedIn si pas d'email).
- Si le site est inaccessible, passe directement a Perplexity + Apollo.
- TOUJOURS appeler **save_enrichment** a la fin, meme avec peu de resultats.
- Le format attendu par save_enrichment est un JSON string :
  '[{{"company_name": "...", "company_domain": "...", "company_url": "...", "contact_name": "...", "contact_first_name": "...", "contact_last_name": "...", "contact_email": "...", "contact_title": "...", "contact_phone": "...", "contact_linkedin": "...", "email_status": "...", "source": "..."}}]'
- Quand tu as fini, appelle **read_enrichment_summary** pour verifier le total.
- ECONOMIE DE TOKENS : pas d'emojis, pas de mise en forme markdown elaboree.
  Ton message final doit etre un resume BREF (2-3 lignes max) : nombre de contacts trouves,
  sources utilisees, problemes rencontres. Rien de plus.
"""


def _extract_domain(url: str) -> str:
    """Extrait le domaine d'une URL."""
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://www.", "http://www.", "https://", "http://"]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


def build_enrich_prompt(
    vertical: VerticalConfig,
    company: dict,
    target_profile: str = "",
    subspecialty: Subspecialty | None = None,
) -> str:
    """Construit le prompt systeme pour l'enrichissement d'UNE entreprise.

    Args:
        vertical: Config de la verticale (cabinets, banques, fonds...)
        company: Dict de l'entreprise a enrichir (name, website_url, domain, city...)
        target_profile: Profil cible optionnel (ex: "Juriste Compliance")
        subspecialty: Sous-specialite a verifier (optionnel)

    Returns:
        Prompt systeme complet pour l'enrichissement.
    """
    domain = company.get("domain", "")
    if not domain:
        domain = _extract_domain(company.get("website_url", ""))

    if target_profile:
        target_profile_section = (
            f"\n## PROFIL CIBLE\n"
            f"L'utilisateur recherche un poste de type : **{target_profile}**\n"
            f"Cible en priorite les decideurs et contacts en lien avec ce profil.\n"
        )
    else:
        target_profile_section = ""

    # Verification : injectee seulement si la verticale a un verify_prompt ET une subspecialty
    if vertical.verify_prompt and subspecialty:
        verification_section = (
            "\n### VERIFICATION DE PERTINENCE\n"
            + vertical.verify_prompt.format(subspecialty=subspecialty.name)
        )
    else:
        verification_section = ""

    return ENRICH_SYSTEM_PROMPT.format(
        company_name=company.get("name", "Inconnu"),
        company_url=company.get("website_url", ""),
        company_domain=domain,
        company_city=company.get("city", ""),
        target_profile_section=target_profile_section,
        enrich_context=vertical.enrich_prompt or "",
        verification_section=verification_section,
        target_contacts=AGENT3_TARGET_CONTACTS,
    )


def build_enrich_user_message(company: dict) -> str:
    """Construit le message utilisateur pour lancer l'enrichissement."""
    name = company.get("name", "Inconnu")
    url = company.get("website_url", "inconnu")
    return (
        f"Enrichis l'entreprise \"{name}\" (site: {url}). "
        f"Trouve les contacts des decideurs. "
        f"Commence par crawler le site, puis complete avec Perplexity et Apollo si besoin. "
        f"Verifie les emails avec NeverBounce. "
        f"Sauvegarde les resultats avec save_enrichment."
    )
