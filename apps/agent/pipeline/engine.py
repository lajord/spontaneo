# ──────────────────────────────────────────────────────────────────
# ENGINE — INFRASTRUCTURE PARTAGEE PAR TOUS LES AGENTS
#
# Contient :
# - build_llm()      : creation du modele Claude
# - emit()           : emission d'events (log, tool_call, progress...)
# - emit_csv_update() : envoi du contenu CSV via callback (SSE)
# - stream_agent()   : lancement d'un ReAct agent avec streaming + retry
#
# Utilise par agent_1_collect, agent_2_verify, agent_3_enrich.
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

import csv
import os
import time
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from config import (
    LLM_MODEL, LLM_MAX_TOKENS, LLM_INTERNAL_RETRIES, LLM_REQUEST_TIMEOUT,
    STREAM_MAX_RETRIES, STREAM_RETRY_DELAY,
    LOG_TOOL_ARGS_MAX_CHARS, LOG_TOOL_RESULT_MAX_CHARS,
)

if TYPE_CHECKING:
    from typing import Callable

load_dotenv()


# ─── LLM ─────────────────────────────────────────────────────────

def build_llm(
    model: str = LLM_MODEL,
    max_tokens: int = LLM_MAX_TOKENS,
) -> ChatAnthropic:
    """Cree l'instance ChatAnthropic."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non trouvee dans le .env")
    return ChatAnthropic(
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        max_retries=LLM_INTERNAL_RETRIES,
        default_request_timeout=LLM_REQUEST_TIMEOUT,
    )


# ─── Events ──────────────────────────────────────────────────────

def emit(event: dict, callback: Callable | None = None) -> None:
    """Emet un event via callback (SSE) ou print (CLI)."""
    if callback:
        callback(event)
        return

    t = event.get("type", "")
    msg = event.get("message", "")

    if t == "phase":
        print()
        print("=" * 60)
        print(f"   {msg}")
        print("=" * 60)
        print()
    elif t == "log":
        phase = event.get("phase", "")
        print(f"  [{phase}] {msg}")
    elif t == "tool_call":
        print(f"  [TOOL] {event.get('name', '')}({event.get('args', '')})")
    elif t == "tool_result":
        print(f"  [RESULT] {msg}")
    elif t == "progress":
        print(f"  {msg}")
    elif t == "error":
        print(f"  [ERREUR] {msg}")
    elif t == "csv_update":
        csv_type = event.get("csv_type", "")
        rows = event.get("rows", [])
        print(f"  [CSV] {csv_type}: {len(rows)} lignes")
    elif t == "done":
        print(f"  {msg}")
    else:
        if msg:
            print(f"  {msg}")


def _read_csv_rows(path: str, delimiter: str = ";") -> list[dict]:
    """Lit un CSV et retourne la liste de dicts."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def emit_csv_update(callback: Callable | None, csv_type: str) -> None:
    """Envoie le contenu actuel d'un CSV via callback."""
    if not callback:
        return
    from tools.candidate_store import CANDIDATES_CSV, VERIFIED_CSV
    from tools.enrichment_store import ENRICHED_CSV

    path_map = {
        "candidates": CANDIDATES_CSV,
        "verified": VERIFIED_CSV,
        "enriched": ENRICHED_CSV,
    }
    path = path_map.get(csv_type)
    if not path:
        return
    rows = _read_csv_rows(path)
    emit({"type": "csv_update", "csv_type": csv_type, "rows": rows}, callback)


# ─── Stream agent ────────────────────────────────────────────────

def stream_agent(
    agent,
    system_prompt: str,
    user_message: str,
    recursion_limit: int,
    phase_name: str,
    log_callback: Callable | None = None,
) -> str:
    """Lance un ReAct agent avec streaming. Retourne le dernier message AI.

    Gere :
    - Parsing des messages AI (texte + tool calls)
    - Parsing des resultats de tools
    - Retry sur rate limit (429) avec backoff exponentiel
    - Emission d'events via callback

    Args:
        agent: Agent LangGraph (create_react_agent)
        system_prompt: Prompt systeme
        user_message: Message utilisateur
        recursion_limit: Limite de recursion LangGraph
        phase_name: Nom de la phase (pour les logs)
        log_callback: Callback pour les events

    Returns:
        Dernier texte AI emis par l'agent.
    """
    
    # --- DEBUG PROMPTS ---
    try:
        with open("debug_prompt.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"PROMPT ({phase_name})\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"[SYSTEM]\n{system_prompt}\n\n")
            f.write(f"[USER]\n{user_message}\n\n")
    except Exception:
        pass

    inputs = {
        "messages": [
            ("system", system_prompt),
            ("user", user_message),
        ],
    }
    config = {"recursion_limit": recursion_limit}
    last_ai_text = ""
    last_tool_name = None

    for attempt in range(STREAM_MAX_RETRIES):
        try:
            for event in agent.stream(inputs, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    messages = node_data.get("messages", [])
                    for msg in messages:
                        if msg.type == "ai":
                            # Texte AI (str ou list de blocks)
                            if msg.content and isinstance(msg.content, str):
                                last_ai_text = msg.content
                                emit({"type": "log", "phase": phase_name, "message": msg.content}, log_callback)
                            elif msg.content and isinstance(msg.content, list):
                                for block in msg.content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        last_ai_text = block["text"]
                                        emit({"type": "log", "phase": phase_name, "message": block["text"]}, log_callback)
                            # Tool calls
                            if msg.tool_calls:
                                for tc in msg.tool_calls:
                                    last_tool_name = tc["name"]
                                    args_short = str(tc["args"])[:LOG_TOOL_ARGS_MAX_CHARS]
                                    emit({"type": "tool_call", "name": tc["name"], "args": args_short}, log_callback)

                            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                                in_t = msg.usage_metadata.get("input_tokens", 0)
                                out_t = msg.usage_metadata.get("output_tokens", 0)
                                emit({
                                    "type": "usage",
                                    "input_tokens": in_t,
                                    "output_tokens": out_t,
                                }, log_callback)
                                emit({
                                    "type": "log",
                                    "phase": phase_name,
                                    "message": f"📊 Tokens: {in_t} in | {out_t} out",
                                }, log_callback)

                        elif msg.type == "tool":
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            emit({"type": "tool_result", "message": content[:LOG_TOOL_RESULT_MAX_CHARS]}, log_callback)
                            # Apres save → envoyer la mise a jour CSV
                            if last_tool_name == "save_candidates":
                                emit_csv_update(log_callback, "candidates")
                            elif last_tool_name == "save_enrichment":
                                emit_csv_update(log_callback, "enriched")

                            # Couper le stream apres read_enrichment_summary :
                            # les donnees sont deja sauvegardees, le dernier appel LLM
                            # ne produirait qu'un resume inutile qui coute des tokens.
                            if last_tool_name == "read_enrichment_summary":
                                return last_ai_text

            return last_ai_text

        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "429" in error_str:
                wait = STREAM_RETRY_DELAY * (attempt + 1)
                emit(
                    {"type": "error", "message": f"[RATE LIMIT] {phase_name} — attente {wait}s (tentative {attempt + 1}/{STREAM_MAX_RETRIES})"},
                    log_callback,
                )
                time.sleep(wait)
            else:
                emit({"type": "error", "message": f"{phase_name} — {e}"}, log_callback)
                raise

    emit(
        {"type": "error", "message": f"{phase_name} — rate limit persistant apres {STREAM_MAX_RETRIES} tentatives"},
        log_callback,
    )
    return last_ai_text
