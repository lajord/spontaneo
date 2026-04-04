from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

from config import (
    LLM_INTERNAL_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    LOG_TOOL_ARGS_MAX_CHARS,
    LOG_TOOL_RESULT_MAX_CHARS,
    STREAM_MAX_RETRIES,
    STREAM_RETRY_DELAY,
)
from runtime import raise_if_cancelled

if TYPE_CHECKING:
    from typing import Callable

load_dotenv()


def _debug_prompt_path() -> Path:
    configured = os.getenv("DEBUG_PROMPT_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "ai-service" / "debug_prompt.txt"


def append_debug_text(text: str) -> None:
    try:
        debug_path = _debug_prompt_path()
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        with debug_path.open("a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


def build_llm(
    model: str = LLM_MODEL,
    max_tokens: int = LLM_MAX_TOKENS,
) -> ChatAnthropic:
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


def emit(event: dict, callback: Callable | None = None) -> None:
    if callback:
        callback(event)
        return

    event_type = event.get("type", "")
    message = event.get("message", "")

    if event_type == "phase":
        print()
        print("=" * 60)
        print(f"   {message}")
        print("=" * 60)
        print()
    elif event_type == "log":
        print(f"  [{event.get('phase', '')}] {message}")
    elif event_type == "tool_call":
        print(f"  [TOOL] {event.get('name', '')}({event.get('args', '')})")
    elif event_type == "tool_result":
        print(f"  [RESULT] {message}")
    elif event_type == "progress":
        print(f"  {message}")
    elif event_type == "error":
        print(f"  [ERREUR] {message}")
    elif event_type == "csv_update":
        print(f"  [CSV] {event.get('csv_type', '')}: {len(event.get('rows', []))} lignes")
    elif event_type == "brief":
        brief_type = event.get("brief_type", "").upper()
        print(f"\033[35m  --- BRIEF {brief_type} ---\033[0m")
        print(f"\033[35m  {message}\033[0m")
    elif event_type == "done":
        print(f"  {message}")
    elif message:
        print(f"  {message}")


def emit_csv_update(callback: Callable | None, csv_type: str) -> None:
    if not callback:
        return

    if csv_type == "candidates":
        from tools.candidate_store import get_candidates_rows

        rows = get_candidates_rows()
    elif csv_type == "enriched":
        from tools.enrichment_store import get_enriched_rows

        rows = get_enriched_rows()
    else:
        return

    emit({"type": "csv_update", "csv_type": csv_type, "rows": rows}, callback)


def append_debug_prompt(phase_name: str, system_prompt: str, user_message: str) -> None:
    append_debug_text(
        f"\n{'=' * 50}\n"
        f"PROMPT ({phase_name})\n"
        f"{'=' * 50}\n\n"
        f"[SYSTEM]\n{system_prompt}\n\n"
        f"[USER]\n{user_message}\n\n"
    )


def stream_agent(
    agent,
    system_prompt: str,
    user_message: str,
    recursion_limit: int,
    phase_name: str,
    log_callback: Callable | None = None,
    quota: int | None = None,
) -> str:
    append_debug_prompt(phase_name, system_prompt, user_message)

    inputs = {
        "messages": [
            ("system", system_prompt),
            ("user", user_message),
        ],
    }
    config = {"recursion_limit": recursion_limit}
    last_ai_text = ""
    last_tool_name = None
    candidate_save_tools = {
        "save_candidates",
        "apollo_search_and_save",
        "google_maps_search_and_save",
        "web_search_legal_and_save",
    }

    for attempt in range(STREAM_MAX_RETRIES):
        try:
            raise_if_cancelled()
            for event in agent.stream(inputs, config=config, stream_mode="updates"):
                raise_if_cancelled()
                for _, node_data in event.items():
                    messages = node_data.get("messages", [])
                    for msg in messages:
                        if msg.type == "ai":
                            if msg.content and isinstance(msg.content, str):
                                last_ai_text = msg.content
                                emit({"type": "log", "phase": phase_name, "message": msg.content}, log_callback)
                            elif msg.content and isinstance(msg.content, list):
                                for block in msg.content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        last_ai_text = block["text"]
                                        emit({"type": "log", "phase": phase_name, "message": block["text"]}, log_callback)

                            if msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    last_tool_name = tool_call["name"]
                                    args_short = str(tool_call["args"])[:LOG_TOOL_ARGS_MAX_CHARS]
                                    emit({"type": "tool_call", "name": tool_call["name"], "args": args_short}, log_callback)
                                    if tool_call["name"] == "crawl_url":
                                        crawl_target = tool_call["args"].get("url", "") if isinstance(tool_call["args"], dict) else ""
                                        if crawl_target:
                                            emit({"type": "log", "phase": phase_name, "message": f"[CRAWL] {crawl_target}"}, log_callback)

                            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                                in_tokens = msg.usage_metadata.get("input_tokens", 0)
                                out_tokens = msg.usage_metadata.get("output_tokens", 0)
                                emit({"type": "usage", "input_tokens": in_tokens, "output_tokens": out_tokens}, log_callback)
                                emit(
                                    {
                                        "type": "log",
                                        "phase": phase_name,
                                        "message": f"Tokens: {in_tokens} in | {out_tokens} out",
                                    },
                                    log_callback,
                                )

                        elif msg.type == "tool":
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            emit(
                                {
                                    "type": "tool_result",
                                    "name": last_tool_name or "",
                                    "message": content[:LOG_TOOL_RESULT_MAX_CHARS],
                                },
                                log_callback,
                            )
                            if last_tool_name == "neverbounce_verify":
                                try:
                                    import json as _json
                                    nb_data = _json.loads(content)
                                    nb_email = nb_data.get("email", "?")
                                    nb_status = nb_data.get("email_status", nb_data.get("result", "?"))
                                    label = nb_status.upper() if nb_status else "?"
                                    emit({"type": "log", "phase": phase_name, "message": f"[NEVERBOUNCE] {nb_email} → {label}"}, log_callback)
                                except Exception:
                                    pass
                            if last_tool_name in candidate_save_tools:
                                emit_csv_update(log_callback, "candidates")
                                if quota is not None:
                                    import re as _re

                                    match = _re.search(r"total:\s*(\d+)", content)
                                    if match and int(match.group(1)) >= quota:
                                        emit(
                                            {
                                                "type": "log",
                                                "phase": phase_name,
                                                "message": f"[QUOTA ATTEINT] {int(match.group(1))}/{quota} entreprises - coupe du stream.",
                                            },
                                            log_callback,
                                        )
                                        return last_ai_text
                            elif last_tool_name == "save_enrichment":
                                emit_csv_update(log_callback, "enriched")

                            if last_tool_name == "read_enrichment_summary":
                                return last_ai_text

            return last_ai_text
        except Exception as e:
            error_str = str(e).lower()
            if "recursion_limit" in error_str or "recursion limit" in error_str:
                emit(
                    {
                        "type": "log",
                        "phase": phase_name,
                        "message": f"[RECURSION LIMIT] Limite atteinte pour {phase_name}. On passe a la suite.",
                    },
                    log_callback,
                )
                return last_ai_text
            if "rate_limit" in error_str or "429" in error_str:
                wait = STREAM_RETRY_DELAY * (attempt + 1)
                emit(
                    {
                        "type": "error",
                        "message": f"[RATE LIMIT] {phase_name} - attente {wait}s (tentative {attempt + 1}/{STREAM_MAX_RETRIES})",
                    },
                    log_callback,
                )
                raise_if_cancelled()
                time.sleep(wait)
            else:
                emit({"type": "error", "message": f"{phase_name} - {e}"}, log_callback)
                raise

    emit(
        {"type": "error", "message": f"{phase_name} - rate limit persistant apres {STREAM_MAX_RETRIES} tentatives"},
        log_callback,
    )
    return last_ai_text
