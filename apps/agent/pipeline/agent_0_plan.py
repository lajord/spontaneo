# ──────────────────────────────────────────────────────────────────
# AGENT 0 — PLANNING / ANALYSE DU JOB TITLE
#
# Role : Analyser le job title + secteur pour produire 2 briefs :
#   - collect_brief  → guide la recherche d'entreprises (Agent 1)
#   - contact_brief  → guide le ciblage de contacts (Agent 3)
#
# Agent 0 est maintenant un agent ReAct capable de lever 
# des ambiguites sur les intitules de poste (via recherche web)
# avant de generer ses briefs.
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import ToolMessage
from tools.perplexity_search import perplexity_search

from pipeline.engine import build_llm, emit, stream_agent
from domains.droit.cabinets import ONTOLOGY as CABINETS_ONTOLOGY
from domains.droit.banques import ONTOLOGY as BANQUES_ONTOLOGY
from domains.droit.fonds import ONTOLOGY as FONDS_ONTOLOGY

ONTOLOGIES = {
    "cabinets": CABINETS_ONTOLOGY,
    "banques": BANQUES_ONTOLOGY,
    "fonds": FONDS_ONTOLOGY,
}

if TYPE_CHECKING:
    from typing import Callable


PLAN_SYSTEM_PROMPT = """Tu es L'ORGANISATEUR (CERVEAU CENTRAL), un expert du marche de l'emploi francais.

## REQUIREMENTS
- PRIORITE ABSOLUE : L'Ontologie fournie en contexte est ta source de verite numero 1.
- CAPACITE DE RECHERCHE : Tu disposes de l'outil `perplexity_search`. UTILISE-LE UNIQUEMENT si une information est manquante dans l'ontologie ou si le job title est trop specifique, un anglicisme rare, ou ambigu, pour situer le poste dans l'organigramme type du secteur.

## INPUT
- Poste vise : {job_title}
- Secteur : {sector_label}
- Localisation : {location}

## ONTOLOGIE DU SECTEUR
{ontology_json}

## LOGIQUE DE TRAITEMENT
1. Analyse de l'Ontologie : Regarde si le job title et le secteur matchent avec une entree.
2. Levee d'ambiguite (si besoin) : Lance une recherche web rapide pour comprendre le metier s'il n'est pas clair.
3. Generation des Briefs : Une fois l'analyse terminee, tu dois produire **EXACTEMENT DEUX SECTIONS** (voir ci-dessous).

---

Tu dois resumer tes conclusions en produisant EXACTEMENT ces deux sections (respecte les titres ##) :

## BRIEF COLLECTE
(Pour l'Agent 1 - DEEP SEARCH. Objectif: Ou chercher et avec quels mots-cles)
- **Mots-cles de recherche** : Liste de mots-cles bases sur le secteur et la specialite.
- **Strategie de sourcing** : Outil a privilegier (ex: "Focus Google Maps pour petites structures locales", "Focus Apollo pour grandes banques").
- **Filtres** : Specialisation precise a valider (si estime necessaire).
- Ca doit etre une sorte de petit manuel, pour donner du contexte a l'agent suivant, tu dois lui donner les informations necessaire
pour que il comprenne en réalité ce qu'il doit chercher, quelle entreprises , type d',entreprise, specialité serait interesser pour recruter
notre candidats
(Directives strictes : Pas de suppositions, on reste sur les faits tires de l'ontologie).

## BRIEF CONTACTS
(Pour l'Agent 3 - ENRICHISSEMENT. Objectif: Qui chercher dans les entreprises trouvees)
- **Profils types** : Liste des titres exacts a cibler.
- **Hierarchie de priorite** : P1 = Contact ideal (la personne qui recrute/manage directement ce poste), P2 = Fallback acceptable, P3 = Dernier recours (RH, DG).
- **Departements cibles** : Noms exacts des services a fouiller sur les sites web.
- **Indicateurs de coherence** : Rappel des lieux geographiques et specialites.

IMPORTANT : Utilise la section `profils_et_contacts` de l'ontologie. Suis scrupuleusement les descriptions 'metier' et 'instruction_ia' pour faire le lien direct entre le poste cible du candidat et l'action des agents suivants.
"""

def _compact_messages(state: dict) -> list:
    """Evite que la memoire n'explose si Agent 0 fait beaucoup de search."""
    messages = state["messages"]
    result = []
    last_ai_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            result.append(ToolMessage(
                content="[COMPACTE]",
                tool_call_id=msg.tool_call_id,
                name=msg.name if hasattr(msg, "name") else "",
            ))
        else:
            result.append(msg)
    return result


def plan(
    secteur: str,
    job_title: str,
    location: str,
    log_callback: Callable | None = None,
) -> tuple[str, str]:
    """Analyse le job title (via LLM + Search si besoin) et produit 2 briefs.

    Args:
        secteur: ID du secteur (cabinets, banques, fonds)
        job_title: Poste vise par l'utilisateur
        location: Ville ciblee
        log_callback: Callback pour le streaming SSE

    Returns:
        (collect_brief, contact_brief)
    """
    emit(
        {"type": "phase", "name": "PLANNING", "message": "AGENT 0 — ANALYSE DU POSTE (Organisateur)"},
        log_callback,
    )

    ontology = ONTOLOGIES.get(secteur, {})
    sector_label = ontology.get("secteur", secteur)
    ontology_json = json.dumps(ontology, ensure_ascii=False, indent=2)

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f"Analyse du poste \"{job_title}\" dans le secteur \"{sector_label}\" a {location}...",
        },
        log_callback,
    )

    system_prompt = PLAN_SYSTEM_PROMPT.format(
        job_title=job_title,
        sector_label=sector_label,
        location=location,
        ontology_json=ontology_json,
    )

    llm = build_llm(max_tokens=2048)
    
    agent = create_react_agent(
        model=llm,
        tools=[perplexity_search],
        prompt=_compact_messages
    )

    user_message = f"Analyse le poste \"{job_title}\". Si son role n'est pas evident dans le contexte de l'ontologie, fais une recherche. Puis, produis les deux briefs au format attendu."

    # L'agent ReAct va decider s'il utilise perplexity_search, puis repondre avec les deux sections.
    text = stream_agent(
        agent=agent,
        system_prompt=system_prompt,
        user_message=user_message,
        recursion_limit=5, # Faible limite car c'est juste de la conception de brief
        phase_name="PLANNING",
        log_callback=log_callback,
    )

    # Parse les 2 sections de la reponse finale
    collect_brief, contact_brief = _parse_briefs(text)

    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f"--- BRIEF COLLECTE (Output Type 1) ---\n{collect_brief}",
        },
        log_callback,
    )
    emit(
        {
            "type": "log",
            "phase": "PLANNING",
            "message": f"--- BRIEF CONTACTS (Output Type 2) ---\n{contact_brief}",
        },
        log_callback,
    )

    return collect_brief, contact_brief


def _parse_briefs(text: str) -> tuple[str, str]:
    """Extrait les sections BRIEF COLLECTE et BRIEF CONTACTS du texte LLM.

    Cherche les marqueurs ## BRIEF COLLECTE et ## BRIEF CONTACTS.
    Si le parsing echoue, retourne le texte complet dans les deux briefs.
    """
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

    collect_brief = collect_match.group(1).strip() if collect_match else text.strip()
    contact_brief = contact_match.group(1).strip() if contact_match else text.strip()

    return collect_brief, contact_brief
