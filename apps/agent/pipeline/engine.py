from __future__ import annotations

import os
import time
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


def stream_agent(
    agent,
    system_prompt: str,
    user_message: str,
    recursion_limit: int,
    phase_name: str,
    log_callback: Callable | None = None,
    quota: int | None = None,
) -> str:
    try:
        with open("debug_prompt.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 50}\n")
            f.write(f"PROMPT ({phase_name})\n")
            f.write(f"{'=' * 50}\n\n")
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
                            emit({"type": "tool_result", "message": content[:LOG_TOOL_RESULT_MAX_CHARS]}, log_callback)
                            if last_tool_name == "save_candidates":
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
