# ──────────────────────────────────────────────────────────────────
# AGENT 1 — COLLECTE DES ENTREPRISES
#
# Role : Trouver des entreprises correspondant a la recherche.
# Input : La config verticale, la requete utilisateur.
# Output : Liste de candidats bruts (nom, url, ville, source).
#
# Cet agent utilise un ReAct agent (LangGraph create_react_agent)
# avec des sources multiples (Apollo, Perplexity, Google Maps)
# pour maximiser la couverture. Il sauvegarde dans un CSV au fil
# de l'eau via save_candidates (apres chaque source).
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

import csv
import os
from typing import TYPE_CHECKING

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import ToolMessage

from config import AGENT1_RECURSION_LIMIT, AGENT1_DEFAULT_BATCH_SIZE
from pipeline.engine import build_llm, emit, stream_agent, emit_csv_update
from pipeline.prompts import build_collect_prompt, build_collect_user_message
from tools.apollo_search import apollo_search
from tools.web_search import web_search_legal
from tools.google_maps_search import google_maps_search
from tools.candidate_store import save_candidates, read_candidates_summary, CANDIDATES_CSV

if TYPE_CHECKING:
    from typing import Callable
    from domains.base import VerticalConfig, Subspecialty

# Valeurs importees depuis config.py
# AGENT1_DEFAULT_BATCH_SIZE = 100  (candidats cibles par iteration)
# AGENT1_RECURSION_LIMIT = 25     (steps LangGraph max)


def _compact_messages(state: dict) -> list:
    """Compacte les vieux resultats de tools pour economiser les tokens.

    Les resultats de recherche (JSON d'entreprises) sont enormes mais inutiles
    une fois que save_candidates a confirme la sauvegarde. On supprime le contenu
    de tous les ToolMessage deja traites par le LLM (avant le dernier AIMessage).
    Les AIMessages sont preserves pour que l'agent garde son raisonnement.
    """
    messages = state["messages"]
    result = []

    # Trouver l'index du dernier AIMessage
    last_ai_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            result.append(ToolMessage(
                content="[RESULTAT DEJA TRAITE — DONNEES SAUVEGARDEES EN CSV]",
                tool_call_id=msg.tool_call_id,
                name=msg.name if hasattr(msg, "name") else "",
            ))
        else:
            result.append(msg)

    # Debug logging
    try:
        with open("debug_prompt.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'-'*40}\nITERATION AGENT 1 (Appel LLM)\n{'-'*40}\n")
            for m in result:
                content = str(m.content)
                if len(content) > 1500:
                    content = content[:1500] + "\n... [TRONQUÉ POUR LE DEBUG]"
                f.write(f"[{m.type.upper()}]\n{content}\n\n")
    except Exception:
        pass

    return result


def _count_candidates() -> int:
    """Compte le nombre total de candidats dans le CSV."""
    if not os.path.exists(CANDIDATES_CSV):
        return 0
    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return sum(1 for _ in reader)


def _read_new_candidates_since(count_before: int) -> list[dict]:
    """Lit les candidats ajoutes depuis count_before."""
    if not os.path.exists(CANDIDATES_CSV):
        return []
    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
    return rows[count_before:]


def collect(
    vertical: VerticalConfig,
    query: str,
    subspecialty: Subspecialty | None,
    log_callback: Callable | None = None,
    batch_size: int = AGENT1_DEFAULT_BATCH_SIZE,
) -> list[dict]:
    """Collecte des entreprises via sources multiples.

    Cree un ReAct agent avec 3 outils de recherche + save_candidates
    + read_candidates_summary. L'agent fait des micro-iterations
    internes (plusieurs appels tools dans un seul run). Apres chaque
    source, il sauvegarde dans le CSV.

    Args:
        vertical: Config de la verticale (cabinets, banques, fonds...)
        query: Requete utilisateur (ville, precisions...)
        subspecialty: Sous-specialite ciblee (optionnel)
        log_callback: Callback pour le streaming d'events
        batch_size: Nombre cible de nouveaux candidats pour cette iteration

    Returns:
        Liste de candidats ajoutes a cette iteration :
        [{"name", "website_url", "domain", "city", "description", "source", "status"}, ...]
    """
    emit(
        {"type": "phase", "name": "COLLECTE", "message": "AGENT 1 — COLLECTE"},
        log_callback,
    )

    # 1. Snapshot du count CSV actuel (pour savoir ce qui a ete ajoute)
    count_before = _count_candidates()

    # 2. Build LLM + agent ReAct
    llm = build_llm()
    tools = [
        apollo_search,
        web_search_legal,
        google_maps_search,
        save_candidates,
        read_candidates_summary,
    ]
    agent = create_react_agent(model=llm, tools=tools, prompt=_compact_messages)

    # 3. Build prompts
    state_info = ""
    if count_before > 0:
        state_info = f"{count_before} entreprises deja collectees."

    system_prompt = build_collect_prompt(
        vertical=vertical,
        query=query,
        subspecialty=subspecialty,
        batch_size=batch_size,
        state_info=state_info,
    )

    user_message = build_collect_user_message(
        current_count=count_before,
        batch_size=batch_size,
    )

    # 4. Stream l'agent
    emit(
        {
            "type": "progress",
            "phase": "collecte",
            "current": count_before,
            "target": count_before + batch_size,
            "message": f"Collecte en cours ({count_before} existants, objectif +{batch_size})...",
        },
        log_callback,
    )

    stream_agent(
        agent=agent,
        system_prompt=system_prompt,
        user_message=user_message,
        recursion_limit=AGENT1_RECURSION_LIMIT,
        phase_name="COLLECTE",
        log_callback=log_callback,
    )

    # 5. Lire ce qui a ete ajoute
    new_candidates = _read_new_candidates_since(count_before)
    count_after = count_before + len(new_candidates)

    emit(
        {
            "type": "progress",
            "phase": "collecte",
            "current": count_after,
            "target": count_before + batch_size,
            "message": f"Collecte terminee : {len(new_candidates)} nouvelles entreprises ({count_after} total).",
        },
        log_callback,
    )

    # 6. Envoyer la mise a jour CSV finale
    emit_csv_update(log_callback, "candidates")

    return new_candidates
