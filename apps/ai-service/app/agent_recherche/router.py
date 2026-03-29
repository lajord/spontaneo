import asyncio
import csv
import json
import logging
import os
import sys
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Ajout du chemin Test_IA_CANDIDATURE au sys.path ────────────────
# Docker : /app/agent/
# Local  : spontaneo/apps/agent/
_DOCKER_PKG = os.path.normpath(os.path.join("/app", "agent"))
_APPS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_LOCAL_PKG = os.path.join(
    _APPS_DIR, "agent"
)

_AGENT_PKG = _DOCKER_PKG if os.path.isdir(_DOCKER_PKG) else _LOCAL_PKG

if _AGENT_PKG not in sys.path:
    sys.path.insert(0, _AGENT_PKG)

import domains.droit  # Register all verticals
from domains.registry import get_vertical
from pipeline.graph import run_pipeline

logger.info(
    f"[AGENT] Agent package path: {_AGENT_PKG} (exists={os.path.isdir(_AGENT_PKG)})"
)

# ─── Chemins CSV ────────────────────────────────────────────────────
_CANDIDATES_CSV = os.path.join(_AGENT_PKG, "candidates.csv")
_VERIFIED_CSV = os.path.join(_AGENT_PKG, "verified.csv")
_ENRICHED_CSV = os.path.join(_AGENT_PKG, "enriched.csv")

ROLES = {1: "Juriste", 2: "Avocat", 3: "Fonds / Investissement"}


# ─── Schemas ─────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    role: int  # 1=Juriste, 2=Avocat
    specialty_num: int  # 1-16
    location: str
    target_count: int = 50
    extra: str = ""


# ─── Helpers ─────────────────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _clear_csvs():
    """Vide les fichiers CSV candidates, verified et enriched."""
    for path in (_CANDIDATES_CSV, _VERIFIED_CSV, _ENRICHED_CSV):
        if os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.truncate(0)


# ─── State ───────────────────────────────────────────────────────────

_run_lock = asyncio.Lock()
_stop_event = threading.Event()


# ─── Endpoints ───────────────────────────────────────────────────────

@router.post("/run")
async def run_agent(request: AgentRunRequest):
    """Lance le pipeline agent et stream les logs en SSE."""

    if _run_lock.locked():
        return StreamingResponse(
            iter([_sse_event({"type": "error", "message": "Un agent est déjà en cours d'exécution."})]),
            media_type="text/event-stream",
        )

    async def event_stream():
        async with _run_lock:
            _stop_event.clear()
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()
            
            # Reset du fichier debug
            try:
                with open("debug_prompt.txt", "w", encoding="utf-8") as f:
                    f.write(f"=== NOUVELLE RECHERCHE ===\nRole: {request.role}\nSpe: {request.specialty_num}\nLieu: {request.location}\n")
            except Exception:
                pass
            
            usage_stats = {"input": 0, "output": 0}

            def log_callback(event: dict):
                if _stop_event.is_set():
                    raise InterruptedError("Agent stopped by user")
                
                if event.get("type") == "usage":
                    usage_stats["input"] += event.get("input_tokens", 0)
                    usage_stats["output"] += event.get("output_tokens", 0)
                    return
                    
                loop.call_soon_threadsafe(queue.put_nowait, event)

            # Trouver la verticale
            if request.role == 2:
                vertical_id = "cabinets"
            elif request.role == 3:
                vertical_id = "fonds"
            else:
                vertical_id = "banques"
                
            try:
                vertical = get_vertical("droit", vertical_id)
            except KeyError:
                yield _sse_event({"type": "error", "message": f"Verticale non trouvée pour role {request.role}"})
                return

            subspecialty = vertical.subspecialties.get(request.specialty_num)
            
            role = ROLES.get(request.role, "Inconnu")

            parts = [
                f"Poste : {role}",
                f"Ville : {request.location}",
            ]
            if subspecialty:
                parts.insert(1, f"Spécialité : {subspecialty.name}")
                
            if request.extra:
                parts.append(f"Précisions : {request.extra}")
            user_query = "\n".join(parts)

            spec_name = subspecialty.name if subspecialty else "Général"

            yield _sse_event({
                "type": "config",
                "role": role,
                "specialty": spec_name,
                "location": request.location,
                "target_count": request.target_count,
            })

            logger.info(
                f"[AGENT] Lancement : {role} / {spec_name} "
                f"/ {request.location} / {request.target_count}"
            )

            def run_in_thread():
                try:
                    run_pipeline(
                        vertical=vertical,
                        query=user_query,
                        subspecialty=subspecialty,
                        target_count=request.target_count,
                        log_callback=log_callback,
                    )
                except InterruptedError:
                    loop.call_soon_threadsafe(
                        queue.put_nowait, {"type": "stopped"}
                    )
                except Exception as e:
                    if not _stop_event.is_set():
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"type": "error", "message": str(e)},
                        )
                finally:
                    loop.call_soon_threadsafe(
                        queue.put_nowait, {"type": "_end"}
                    )

            thread_task = loop.run_in_executor(None, run_in_thread)

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if _stop_event.is_set():
                        yield _sse_event({
                            "type": "stopped",
                            "message": "Agent arrêté par l'utilisateur.",
                        })
                        break
                    yield ": heartbeat\n\n"
                    continue

                if event.get("type") == "_end":
                    break
                if event.get("type") == "stopped":
                    yield _sse_event({
                        "type": "stopped",
                        "message": "Agent arrêté par l'utilisateur.",
                    })
                    break

                yield _sse_event(event)
                
            in_t = usage_stats["input"]
            out_t = usage_stats["output"]
            if in_t > 0 or out_t > 0:
                cost_usd = (in_t / 1_000_000 * 3.0) + (out_t / 1_000_000 * 15.0)
                cost_eur = cost_usd * 0.86
                yield _sse_event({
                    "type": "log",
                    "phase": "BILLING",
                    "message": f"💰 Coût estimé : {cost_eur:.4f}€ (Input: {in_t} | Output: {out_t})"
                })

            try:
                await asyncio.wait_for(thread_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(
                    "[AGENT] Thread n'a pas terminé dans les 5s après stop"
                )

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
    """Force l'arrêt de l'agent en cours et vide les CSV."""
    if not _run_lock.locked():
        return {"status": "idle", "message": "Aucun agent en cours."}

    _stop_event.set()
    _clear_csvs()
    logger.info("[AGENT] Stop demandé — CSV vidés.")
    return {"status": "stopped", "message": "Signal d'arrêt envoyé, CSV vidés."}


@router.get("/specialties")
async def get_specialties():
    """Retourne la liste des spécialités et rôles disponibles."""
    # On prend la verticale "cabinets" comme référence pour les spécialités front
    vertical = get_vertical("droit", "cabinets")
    specialties = {
        sub.id: {"name_fr": sub.name, "name_en": sub.name}
        for sub in vertical.subspecialties.values()
    }
    return {
        "roles": ROLES,
        "specialties": specialties,
    }


@router.get("/csv/{csv_type}")
async def get_csv(csv_type: str):
    """Retourne le contenu actuel d'un CSV (candidates, verified ou enriched)."""
    if csv_type == "candidates":
        rows = _read_csv(_CANDIDATES_CSV)
    elif csv_type == "verified":
        rows = _read_csv(_VERIFIED_CSV)
    elif csv_type == "enriched":
        rows = _read_csv(_ENRICHED_CSV)
    else:
        return {
            "error": f"Type CSV invalide: {csv_type}. "
            "Utilisez 'candidates', 'verified' ou 'enriched'."
        }
    return {"csv_type": csv_type, "count": len(rows), "rows": rows}
