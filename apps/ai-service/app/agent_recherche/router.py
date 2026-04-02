import asyncio
import csv
import json
import logging
import math
import os
import sys
import threading

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_DOCKER_PKG = os.path.normpath(os.path.join("/app", "agent"))
_APPS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_LOCAL_PKG = os.path.join(_APPS_DIR, "agent")
_AGENT_PKG = _DOCKER_PKG if os.path.isdir(_DOCKER_PKG) else _LOCAL_PKG

if _AGENT_PKG not in sys.path:
    sys.path.insert(0, _AGENT_PKG)

from pipeline.engine import append_debug_text
from pipeline.graph import run_pipeline
from runtime import set_cancel_checker

logger.info(
    f"[AGENT] Agent package path: {_AGENT_PKG} (exists={os.path.isdir(_AGENT_PKG)})"
)

_CANDIDATES_CSV = os.path.join(_AGENT_PKG, "candidates.csv")
_VERIFIED_CSV = os.path.join(_AGENT_PKG, "verified.csv")
_ENRICHED_CSV = os.path.join(_AGENT_PKG, "enriched.csv")

SECTEURS = {
    "cabinet_avocat": "Cabinet Avocat",
    "banque": "Banque",
    "fond_investissement": "Fond d'investissement",
}

CREDITS_PER_COMPANY = 2


class AgentRunRequest(BaseModel):
    secteur: str
    sous_secteur: str = ""
    job_title: str
    location: str
    credit_budget: int | None = None
    target_count: int | None = None
    extra: str = ""
    user_id: str = ""
    job_id: str = ""
    campaign_id: str
    mode: str = "full"  # "full" | "collect" | "enrich"


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _resolve_target_count(request: AgentRunRequest) -> int:
    if request.credit_budget is not None:
        return max(1, math.floor(request.credit_budget / CREDITS_PER_COMPANY))
    if request.target_count is not None:
        return max(1, request.target_count)
    return 50


@router.post("/run")
async def run_agent(request: Request, payload: AgentRunRequest):
    """Lance le pipeline agent et stream les logs en SSE."""
    stop_event = threading.Event()

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        target_count = _resolve_target_count(payload)

        append_debug_text(
            "\n" + "=" * 60 + "\n"
            "=== NOUVELLE RECHERCHE ===\n"
            f"Secteur: {payload.secteur}\n"
            f"Sous-secteur: {payload.sous_secteur}\n"
            f"Job Title: {payload.job_title}\n"
            f"Lieu: {payload.location}\n"
            f"Campaign ID: {payload.campaign_id}\n"
            f"Job ID: {payload.job_id}\n"
            f"Credit budget: {payload.credit_budget}\n"
        )

        usage_stats = {"input": 0, "output": 0}

        def log_callback(event: dict):
            if stop_event.is_set():
                raise InterruptedError("Agent stopped by user")

            if event.get("type") == "usage":
                usage_stats["input"] += event.get("input_tokens", 0)
                usage_stats["output"] += event.get("output_tokens", 0)
                return

            loop.call_soon_threadsafe(queue.put_nowait, event)

        secteur_to_vertical = {
            "cabinet_avocat": "cabinets",
            "banque": "banques",
            "fond_investissement": "fonds",
        }
        vertical_id = secteur_to_vertical.get(payload.secteur, "cabinets")

        if vertical_id not in ("cabinets", "banques", "fonds"):
            yield _sse_event({"type": "error", "message": f"Secteur inconnu : '{payload.secteur}'"})
            return

        secteur_label = SECTEURS.get(payload.secteur, payload.secteur)
        parts = [
            f"Poste visé : {payload.job_title}",
            f"Secteur : {secteur_label}",
            f"Ville : {payload.location}",
        ]
        if payload.sous_secteur:
            parts.append(f"Sous-secteur : {payload.sous_secteur}")
        if payload.extra:
            parts.append(f"Précisions : {payload.extra}")

        user_query = "\n".join(parts)

        yield _sse_event({
            "type": "config",
            "secteur": secteur_label,
            "sous_secteur": payload.sous_secteur,
            "job_title": payload.job_title,
            "location": payload.location,
            "credit_budget": payload.credit_budget,
            "target_count": target_count,
            "campaign_id": payload.campaign_id,
            "job_id": payload.job_id,
        })

        logger.info(
            f"[AGENT] Lancement : {secteur_label} / {payload.sous_secteur or '-'} / "
            f"{payload.job_title} / {payload.location} / target={target_count} / job={payload.job_id}"
        )

        def run_in_thread():
            try:
                set_cancel_checker(stop_event.is_set)
                run_pipeline(
                    secteur=vertical_id,
                    query=user_query,
                    job_title=payload.job_title,
                    target_count=target_count,
                    log_callback=log_callback,
                    user_id=payload.user_id or "anonymous",
                    job_id=payload.job_id or None,
                    campaign_id=payload.campaign_id,
                    location=payload.location,
                    mode=payload.mode,
                )
            except InterruptedError:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "stopped"})
            except Exception as e:
                if not stop_event.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "_end"})

        thread_task = loop.run_in_executor(None, run_in_thread)

        try:
            while True:
                if await request.is_disconnected():
                    stop_event.set()
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if stop_event.is_set():
                        yield _sse_event({"type": "stopped", "message": "Agent arrêté."})
                        break
                    yield ": heartbeat\n\n"
                    continue

                if event.get("type") == "_end":
                    break
                if event.get("type") == "stopped":
                    yield _sse_event({"type": "stopped", "message": "Agent arrêté."})
                    break

                yield _sse_event(event)
        except asyncio.CancelledError:
            stop_event.set()
            raise
        finally:
            stop_event.set()
            in_t = usage_stats["input"]
            out_t = usage_stats["output"]
            if in_t > 0 or out_t > 0:
                cost_usd = (in_t / 1_000_000 * 3.0) + (out_t / 1_000_000 * 15.0)
                cost_eur = cost_usd * 0.86
                yield _sse_event({
                    "type": "log",
                    "phase": "BILLING",
                    "message": f"Cout estime : {cost_eur:.4f} EUR (Input: {in_t} | Output: {out_t})",
                })
            try:
                await asyncio.wait_for(thread_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("[AGENT] Thread n'a pas termine dans les 5s apres stop")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop")
async def stop_agent():
    return {
        "status": "deprecated",
        "message": "Le stop direct n'est plus utilise. Annulez le job via le worker.",
    }


@router.get("/specialties")
async def get_specialties():
    return {"secteurs": SECTEURS}


@router.get("/csv/{csv_type}")
async def get_csv(csv_type: str):
    if csv_type == "candidates":
        rows = _read_csv(_CANDIDATES_CSV)
    elif csv_type == "verified":
        rows = _read_csv(_VERIFIED_CSV)
    elif csv_type == "enriched":
        rows = _read_csv(_ENRICHED_CSV)
    else:
        return {"error": f"Type CSV invalide: {csv_type}."}
    return {"csv_type": csv_type, "count": len(rows), "rows": rows}
