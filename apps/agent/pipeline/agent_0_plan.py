from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import create_react_agent

from domains.droit.banques import ONTOLOGY as BANQUES_ONTOLOGY
from domains.droit.cabinets import ONTOLOGY as CABINETS_ONTOLOGY
from domains.droit.fonds import ONTOLOGY as FONDS_ONTOLOGY
from pipeline.engine import build_llm, emit, stream_agent
from tools.perplexity_search import perplexity_search

ONTOLOGIES = {
    "cabinets": CABINETS_ONTOLOGY,
    "banques": BANQUES_ONTOLOGY,
    "fonds": FONDS_ONTOLOGY,
}

if TYPE_CHECKING:
    from typing import Callable


PLAN_SYSTEM_PROMPT = """Tu es L'ORGANISATEUR (CERVEAU CENTRAL), un expert du marche de l'emploi francais.

## REQUIREMENTS
- PRIORITE ABSOLUE : l'ontologie fournie en contexte est ta source de verite numero 1.
- CAPACITE DE RECHERCHE : tu disposes de l'outil `perplexity_search`. Utilise-le UNIQUEMENT si une information est manquante dans l'ontologie ou si le job title est trop specifique, ambigu, ou difficile a situer dans l'organigramme type du secteur.

## INPUT
- Poste vise : {job_title}
- Secteur : {sector_label}
- Localisation : {location}

## ONTOLOGIE DU SECTEUR
{ontology_json}

## LOGIQUE DE TRAITEMENT
1. Analyse d'abord l'ontologie.
2. Si besoin, leve une ambiguite avec une recherche rapide.
3. Puis produis EXACTEMENT DEUX SECTIONS.

---

Tu dois resumer tes conclusions en produisant EXACTEMENT ces deux sections (respecte les titres `##`) :

## BRIEF COLLECTE
(Pour l'Agent 1 - DEEP SEARCH. Objectif : quelle entreprise chercher)
- Ce brief doit etre COURT et CONDENSE.
- 3 a 5 lignes maximum.
- Le but est juste de repondre a cette question : "Qu'est-ce que je dois chercher comme entreprise ?"
- Ne donne pas une longue liste de mots-cles.
- Ne parle pas de verification, de scoring, ou de logique complexe.
- Dis simplement :
  - quel type d'entreprise chercher
  - quelle specialite / pratique / sous-secteur viser
  - eventuellement quelle taille ou quel style de structure viser si c'est pertinent
- Pas de suppositions : reste sur les faits tires de l'ontologie.

## BRIEF CONTACTS
(Pour l'Agent 3 - ENRICHISSEMENT. Objectif : quelle personne essayer de trouver)
- Ce brief doit etre COURT et CONDENSE.
- 3 a 5 lignes maximum.
- Le but est simple : dire a l'agent enrichissement quelle personne il doit essayer de trouver dans l'entreprise.
- Dis seulement :
  - quels roles / specialites sont prioritaires
  - quels fallback sont acceptables
  - quel service / pole / pratique viser si c'est utile
- Si le secteur concerne un cabinet, dis explicitement a l'agent enrichissement qu'il doit verifier que le contact correspond bien a la bonne pratique / specialite avant de le garder.
- N'ajoute pas de longue liste de mots-cles ni d'explications inutiles.

IMPORTANT : utilise la section `profils_et_contacts` de l'ontologie. Suis scrupuleusement les descriptions `metier` et `instruction_ia`, puis condense fortement l'information.
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
        prompt=_compact_messages,
    )

    user_message = (
        f'Analyse le poste "{job_title}". '
        f"Si son role n'est pas evident dans le contexte de l'ontologie, fais une recherche. "
        "Puis produis les deux briefs au format attendu."
    )

    text = stream_agent(
        agent=agent,
        system_prompt=system_prompt,
        user_message=user_message,
        recursion_limit=5,
        phase_name="PLANNING",
        log_callback=log_callback,
    )

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

    collect_brief = collect_match.group(1).strip() if collect_match else text.strip()
    contact_brief = contact_match.group(1).strip() if contact_match else text.strip()

    return collect_brief, contact_brief
