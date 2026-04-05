from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import create_react_agent

from domains.droit.banques import ONTOLOGY as BANQUES_ONTOLOGY
from domains.droit.cabinets import ONTOLOGY as CABINETS_ONTOLOGY
from domains.droit.entreprises import ONTOLOGY as ENTREPRISES_ONTOLOGY
from domains.droit.fonds import ONTOLOGY as FONDS_ONTOLOGY
from pipeline.engine import append_debug_prompt, build_llm, emit, stream_agent
from tools.perplexity_search import perplexity_search

if TYPE_CHECKING:
    from typing import Callable


ONTOLOGIES = {
    "cabinets": CABINETS_ONTOLOGY,
    "banques": BANQUES_ONTOLOGY,
    "fonds": FONDS_ONTOLOGY,
    "entreprises": ENTREPRISES_ONTOLOGY,
}


EXTRACTION_SYSTEM_PROMPT = """Tu es un analyste metier charge d'extraire les signaux les plus utiles a partir d'un document sectoriel.

REGLES
- Tu travailles d'abord a partir du document fourni. N'invente rien hors document.
- Tu dois relier le contenu du document a la recherche de l'utilisateur, en particulier au job title vise.
- Tu dois produire un seul petit paragraphe en texte brut.
- Pas de titre, pas de puces, pas de liste numerotee, pas de markdown.
- Tu dois resumer uniquement les informations utiles pour comprendre ou ce profil a du sens et quel type d'interlocuteurs existent dans ce secteur.
- Si le document est pauvre, tu le dis sobrement et tu restes ancre dans ce qui est visible.
"""


BRIEF_SYSTEM_PROMPT = """Tu es l'organisateur central du pipeline de candidature spontanee.

Tu recois :
- l'ontologie du secteur, qui reste la source de verite numero 1 ;
- un paragraphe d'extraction issu du document sectoriel ;
- deux enrichissements Perplexity : marche/etablissements puis persona/contacts.

TA MISSION
- Croiser ces signaux sans sortir du cadre du secteur.
- Si Perplexity est vague, fragile ou hors sujet, revenir a l'ontologie.
- Produire EXACTEMENT deux sections :

## BRIEF COLLECTE
<un mini paragraphe brut>

## BRIEF CONTACTS
<un mini paragraphe brut>

CONTRAINTES BRIEF COLLECTE
- Le brief est une LISTE DE PHRASES-CLES separees par des virgules.
- Chaque phrase-cle = type de structure + specialite si pertinente.
- Exemples pour les banques : "Banque financement retail, Banque financement corporate, Banque privee, Banque publique"
- Exemples pour les cabinets : "Cabinet avocat specialite M&A, Cabinet avocat specialite droit social, Cabinet avocat droit des affaires" ou simplement "Cabinet d'avocats" si aucune specialite n'est requise.
- Exemples pour les fonds : "Fond d'investissement private equity, Fond d'investissement immobilier"
- INTERDIT : citer des noms d'entreprises (pas de "BNP Paribas", "Natixis", "CMS Francis Lefebvre").
- INTERDIT : faire des paragraphes descriptifs. Juste des phrases-cles courtes.
- Ces phrases-cles seront utilisees directement comme requetes de recherche.

CONTRAINTES BRIEF CONTACTS
- 2 a 3 lignes maximum.
- Texte brut uniquement.
- Aucun sous-titre, aucune puce, aucune liste.
- Repondre simplement a : "Quelle personne faut-il essayer de trouver dans l'entreprise ?"
- Citer 3 a 4 titres de poste MAXIMUM, pas plus.
- UNIQUEMENT des titres en francais, simples et courants. Exemples : "Directeur juridique", "DRH", "DAF", "Associe", "Responsable financement", "Directeur commercial".
- INTERDIT : titres en anglais (pas de "Head of", "General Counsel", "Managing Partner", "Chief"), titres ultra-specifiques (pas de "Responsable Juridique Financements Structures"), acronymes anglais.
- TOUJOURS inclure au moins un poste evident et transversal comme DRH ou Responsable RH en fallback.
- Si le secteur concerne un cabinet, preciser la specialite a verifier (ex: "Associe specialise en M&A" et non "Head of M&A Practice").
- Les titres doivent etre cherchables : quelqu'un doit pouvoir taper "{titre} {entreprise} {ville}" sur Google et trouver la personne.

FORMAT
- Respecte strictement les titres `## BRIEF COLLECTE` et `## BRIEF CONTACTS`.
- N'ajoute rien avant, entre ou apres ces deux sections.
"""


RESEARCH_SYSTEM_PROMPT = """Tu es un agent de recherche metier. Tu dois comprendre un poste pour aider a cibler des candidatures spontanees.

TON ROLE
- Comprendre le METIER, pas cartographier le marche.
- Produire une analyse GENERIQUE : types de structures, specialites, profils de contact.
- Ta sortie sera utilisee par un autre agent pour chercher des entreprises concretes. Toi, tu fournis le cadre.

DEROULEMENT STRICT — 3 RECHERCHES, PAS PLUS
Tu fais EXACTEMENT 3 appels a `perplexity_search`, un par question. Pas de 4e recherche.

Recherche 1 — COMPRENDRE LE METIER
"En quoi consiste concretement le metier de [job_title] ? Quelles sont ses missions principales ?"

Recherche 2 — TYPES DE STRUCTURES
"Quel genre de structure emploie un [job_title] ? Quelles specialites, departements ou pratiques sont concernes ?"
→ On attend des CATEGORIES (ex: cabinets d'affaires specialises en M&A, ETI industrielles, fonds d'investissement)
→ JAMAIS de noms propres, JAMAIS de villes.

Recherche 3 — PERSONA CONTACT
"Si je veux envoyer une candidature spontanee pour un poste de [job_title], a quel type de personne dois-je m'adresser ?"
→ On attend des TITRES (ex: associe M&A, DRH, responsable du departement corporate, managing partner)
→ JAMAIS de noms propres, JAMAIS de villes.

INTERDIT (STRICT)
- JAMAIS de ville, localisation ou departement geographique.
- JAMAIS de noms propres (cabinets, personnes, marques).
- JAMAIS de recherches "recrutement", "offres d'emploi" ou "liste de cabinets".

APRES LES 3 RECHERCHES
Ecris IMMEDIATEMENT ta synthese finale. Ne fais pas de recherche supplementaire.

SORTIE FINALE — EXACTEMENT ces deux sections :

## RECHERCHE MARCHE
<un paragraphe brut : types de structures et specialites qui recrutent ce profil, sans aucun nom propre>

## RECHERCHE CONTACTS
<un paragraphe brut : type de personne a contacter (titre, service, niveau hierarchique), sans aucun nom propre>

CONTRAINTES DE FORMAT
- Texte brut, pas de puces, pas de listes, pas de markdown.
- AUCUN nom propre dans la sortie finale.
- N'ajoute rien avant, entre ou apres ces deux sections.
"""


def _compact_research_messages(state: dict) -> list:
    """Compacte les vieux retours Perplexity pendant la phase 2."""
    messages = state["messages"]
    result = []
    last_ai_idx = -1

    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            result.append(
                ToolMessage(
                    content="[COMPACTE]",
                    tool_call_id=msg.tool_call_id,
                    name=msg.name if hasattr(msg, "name") else "",
                )
            )
        else:
            result.append(msg)

    return result


def _llm_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return str(content).strip()

    chunks: list[str] = []
    for block in content:
        if isinstance(block, str):
            text = block
        elif hasattr(block, "text"):
            text = getattr(block, "text", "")
        elif isinstance(block, dict):
            text = block.get("text", "") if block.get("type") == "text" else ""
        else:
            text = ""

        if text and text.strip():
            chunks.append(text.strip())

    return "\n".join(chunks).strip()


def _invoke_llm_phase(
    *,
    phase_name: str,
    system_prompt: str,
    user_message: str,
    log_callback: Callable | None = None,
    max_tokens: int = 1400,
) -> str:
    append_debug_prompt(phase_name, system_prompt, user_message)

    llm = build_llm(max_tokens=max_tokens)
    response = llm.invoke(
        [
            ("system", system_prompt),
            ("user", user_message),
        ]
    )
    text = _llm_content_to_text(response.content)

    usage = getattr(response, "usage_metadata", None) or {}
    in_tokens = usage.get("input_tokens", 0)
    out_tokens = usage.get("output_tokens", 0)
    if in_tokens or out_tokens:
        emit(
            {
                "type": "log",
                "phase": "PLANNING",
                "message": f"{phase_name} - Tokens: {in_tokens} in | {out_tokens} out",
            },
            log_callback,
        )

    return text.strip()


def _build_extraction_prompt(
    *,
    job_title: str,
    sector_label: str,
    location: str,
    ontology_json: str,
) -> str:
    return (
        f"Poste vise : {job_title}\n"
        f"Secteur : {sector_label}\n"
        f"Localisation / contexte utilisateur : {location or 'NON PRECISE'}\n\n"
        "Document sectoriel a analyser :\n"
        f"{ontology_json}\n\n"
        "A partir du document et de la recherche de l'utilisateur, ecris un petit paragraphe de synthese qui renvoie "
        "uniquement les informations du document les plus pertinentes pour ce job title. "
        "Le paragraphe doit expliquer quel type de structures, de specialites ou de pratiques sont les plus coherents, "
        "et quels interlocuteurs ou poles ressortent du document."
    )


def _build_phase2_user_message(
    *,
    job_title: str,
    sector_label: str,
    ontology_json: str,
    extraction_summary: str,
) -> str:
    return (
        f"Poste vise : {job_title}\n"
        f"Secteur : {sector_label}\n\n"
        "ONTOLOGIE DU SECTEUR\n"
        f"{ontology_json}\n\n"
        "EXTRACTION DOCUMENTAIRE\n"
        f"{extraction_summary}\n\n"
        "Travaille en deux temps : d'abord les structures a viser, puis les personnes a contacter. "
        "Utilise Perplexity autant que necessaire pour adapter ta recherche, mais arrete-toi des que tu as assez de signal utile et non repetitif. "
        "Ta synthese finale doit contenir exactement `## RECHERCHE MARCHE` puis `## RECHERCHE CONTACTS`."
    )


def _build_phase3_prompt(
    *,
    job_title: str,
    sector_label: str,
    location: str,
    ontology_json: str,
    extraction_summary: str,
    market_research: str,
    contact_research: str,
) -> str:
    return (
        f"Poste vise : {job_title}\n"
        f"Secteur : {sector_label}\n"
        f"Localisation / contexte utilisateur : {location or 'NON PRECISE'}\n\n"
        "ONTOLOGIE DU SECTEUR\n"
        f"{ontology_json}\n\n"
        "EXTRACTION DOCUMENTAIRE\n"
        f"{extraction_summary}\n\n"
        "PERPLEXITY METIER / MARCHE\n"
        f"{market_research}\n\n"
        "PERPLEXITY PERSONA / CONTACT\n"
        f"{contact_research}"
    )


def _cleanup_brief(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: list[str] = []

    for line in lines:
        if re.match(r"^\(.*\)$", line):
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        cleaned.append(line)

    return re.sub(r"\s+", " ", " ".join(cleaned)).strip()


def _parse_research_sections(text: str) -> tuple[str, str]:
    market_match = re.search(
        r"##\s*RECHERCHE\s+MARCHE\s*\n(.*?)(?=##\s*RECHERCHE\s+CONTACTS|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    contact_match = re.search(
        r"##\s*RECHERCHE\s+CONTACTS\s*\n(.*?)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    market_raw = market_match.group(1).strip() if market_match else text.strip()
    contact_raw = contact_match.group(1).strip() if contact_match else text.strip()

    return _cleanup_brief(market_raw), _cleanup_brief(contact_raw)


def plan(
    secteur: str,
    job_title: str,
    location: str,
    log_callback: Callable | None = None,
) -> tuple[str, str]:
    """Analyse le job title et produit 2 briefs."""
    emit(
        {"type": "phase", "name": "PLANNING", "message": "AGENT 0 - ANALYSE DU POSTE (Organisateur)"},
        log_callback,
    )

    ontology = ONTOLOGIES.get(secteur, {})
    sector_label = ontology.get("secteur", secteur)
    ontology_json = json.dumps(ontology, ensure_ascii=False, indent=2)

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f'Analyse du poste "{job_title}" dans le secteur "{sector_label}" a {location}...',
        },
        log_callback,
    )

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": "Phase 1/3 - Extraction des signaux utiles depuis l'ontologie sectorielle.",
        },
        log_callback,
    )
    extraction_summary = _invoke_llm_phase(
        phase_name="PLANNING - EXTRACTION",
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_message=_build_extraction_prompt(
            job_title=job_title,
            sector_label=sector_label,
            location=location,
            ontology_json=ontology_json,
        ),
        log_callback=log_callback,
        max_tokens=900,
    )
    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f"[EXTRACTION]\n{extraction_summary}",
        },
        log_callback,
    )

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": "Phase 2/3 - Recherche agentique via Perplexity sur le marche puis sur les contacts.",
        },
        log_callback,
    )
    phase2_llm = build_llm(max_tokens=1600)
    research_agent = create_react_agent(
        model=phase2_llm,
        tools=[perplexity_search],
        prompt=_compact_research_messages,
    )
    research_text = stream_agent(
        agent=research_agent,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        user_message=_build_phase2_user_message(
            job_title=job_title,
            sector_label=sector_label,
            ontology_json=ontology_json,
            extraction_summary=extraction_summary,
        ),
        recursion_limit=14,
        phase_name="PLANNING - RECHERCHE",
        log_callback=log_callback,
    )
    market_research, contact_research = _parse_research_sections(research_text)

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f"[RECHERCHE MARCHE]\n{market_research}",
        },
        log_callback,
    )
    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f"[RECHERCHE CONTACTS]\n{contact_research}",
        },
        log_callback,
    )

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": "Phase 3/3 - Generation finale des deux briefs via appel LLM.",
        },
        log_callback,
    )
    phase3_text = _invoke_llm_phase(
        phase_name="PLANNING - BRIEFS",
        system_prompt=BRIEF_SYSTEM_PROMPT,
        user_message=_build_phase3_prompt(
            job_title=job_title,
            sector_label=sector_label,
            location=location,
            ontology_json=ontology_json,
            extraction_summary=extraction_summary,
            market_research=market_research,
            contact_research=contact_research,
        ),
        log_callback=log_callback,
        max_tokens=1200,
    )

    collect_brief, contact_brief = _parse_briefs(phase3_text)

    emit(
        {
            "type": "brief",
            "brief_type": "collecte",
            "message": collect_brief,
        },
        log_callback,
    )
    emit(
        {
            "type": "brief",
            "brief_type": "contacts",
            "message": contact_brief,
        },
        log_callback,
    )

    return collect_brief, contact_brief


def _parse_briefs(text: str) -> tuple[str, str]:
    """Extrait les sections BRIEF COLLECTE et BRIEF CONTACTS du texte LLM."""
    collect_match = re.search(
        r"##\s*BRIEF\s+COLLECTE\s*\n(.*?)(?=##\s*BRIEF\s+CONTACTS|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    contact_match = re.search(
        r"##\s*BRIEF\s+CONTACTS\s*\n(.*?)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    collect_raw = collect_match.group(1).strip() if collect_match else text.strip()
    contact_raw = contact_match.group(1).strip() if contact_match else text.strip()

    collect_brief = _cleanup_brief(collect_raw)
    contact_brief = _cleanup_brief(contact_raw)

    return collect_brief, contact_brief
