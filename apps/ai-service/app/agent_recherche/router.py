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
# router.py est dans : spontaneo/apps/ai-service/app/agent_recherche/
#   dirname = agent_recherche/ -> .. = app/ -> .. = ai-service/ -> .. = apps/
_APPS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_AGENT_PKG = os.path.join(
    _APPS_DIR, "Test_IA_CANDIDATURE", "Agent_Extraction_Data"
)

if _AGENT_PKG not in sys.path:
    sys.path.insert(0, _AGENT_PKG)

logger.info(
    f"[AGENT] Agent package path: {_AGENT_PKG} (exists={os.path.isdir(_AGENT_PKG)})"
)

# ─── Chemins CSV ────────────────────────────────────────────────────
_CANDIDATES_CSV = os.path.join(_AGENT_PKG, "candidates.csv")
_VERIFIED_CSV = os.path.join(_AGENT_PKG, "verified.csv")

# ─── Spécialités (miroir de main.py) ────────────────────────────────

SPECIALTIES = {
    1:  {"name_fr": "Contentieux des Affaires", "name_en": "Business Litigation",
         "keywords_en": ["business litigation", "commercial disputes", "trial lawyer"],
         "keywords_fr": ["contentieux des affaires", "litiges commerciaux"]},
    2:  {"name_fr": "Arbitrage", "name_en": "Arbitration",
         "keywords_en": ["arbitration", "international arbitration", "dispute resolution"],
         "keywords_fr": ["arbitrage", "arbitrage international"]},
    3:  {"name_fr": "Concurrence / Antitrust", "name_en": "Competition & Antitrust",
         "keywords_en": ["antitrust", "competition law", "merger control"],
         "keywords_fr": ["droit de la concurrence", "antitrust"]},
    4:  {"name_fr": "Distribution & Conso", "name_en": "Distribution & Consumer",
         "keywords_en": ["distribution law", "consumer protection", "retail law"],
         "keywords_fr": ["droit de la distribution", "droit de la consommation"]},
    5:  {"name_fr": "IP / IT", "name_en": "Intellectual Property & Tech",
         "keywords_en": ["intellectual property", "patent law", "IT law", "technology law"],
         "keywords_fr": ["propriété intellectuelle", "droit du numérique", "droit des nouvelles technologies"]},
    6:  {"name_fr": "Droit Fiscal", "name_en": "Tax Law",
         "keywords_en": ["tax law", "tax advisory", "fiscal law"],
         "keywords_fr": ["droit fiscal", "fiscalité"]},
    7:  {"name_fr": "Droit Boursier", "name_en": "Capital Markets",
         "keywords_en": ["capital markets", "securities law", "stock exchange law"],
         "keywords_fr": ["droit boursier", "marchés de capitaux"]},
    8:  {"name_fr": "Debt Finance", "name_en": "Debt Finance",
         "keywords_en": ["debt finance", "loan agreements", "structured finance"],
         "keywords_fr": ["financement de dette", "financement structuré"]},
    9:  {"name_fr": "Corporate M&A / Fusions-Acquisitions", "name_en": "Corporate M&A",
         "keywords_en": ["mergers acquisitions", "M&A", "corporate law"],
         "keywords_fr": ["fusions-acquisitions", "droit des sociétés", "M&A"]},
    10: {"name_fr": "Restructuring / Entreprises en difficulté", "name_en": "Restructuring",
         "keywords_en": ["restructuring", "insolvency", "bankruptcy law"],
         "keywords_fr": ["restructuration", "entreprises en difficulté", "procédures collectives"]},
    11: {"name_fr": "Private Equity / Capital-Investissement", "name_en": "Private Equity",
         "keywords_en": ["private equity", "venture capital", "investment fund"],
         "keywords_fr": ["private equity", "capital-investissement", "fonds d'investissement"]},
    12: {"name_fr": "Droit Immobilier / Real Estate", "name_en": "Real Estate",
         "keywords_en": ["real estate law", "property law", "construction law"],
         "keywords_fr": ["droit immobilier", "droit de la construction"]},
    13: {"name_fr": "Financement de Projets", "name_en": "Project Finance",
         "keywords_en": ["project finance", "infrastructure finance", "PPP"],
         "keywords_fr": ["financement de projets", "project finance"]},
    14: {"name_fr": "Banque & Finance", "name_en": "Banking & Finance",
         "keywords_en": ["banking law", "financial regulation", "banking finance"],
         "keywords_fr": ["droit bancaire", "droit financier", "banque et finance"]},
    15: {"name_fr": "Droit Social", "name_en": "Employment & Labor Law",
         "keywords_en": ["employment law", "labor law", "HR legal"],
         "keywords_fr": ["droit social", "droit du travail"]},
    16: {"name_fr": "Droit Pénal", "name_en": "Criminal Law",
         "keywords_en": ["criminal law", "white collar crime", "criminal defense"],
         "keywords_fr": ["droit pénal", "droit pénal des affaires"]},
}

ROLES = {1: "Juriste", 2: "Avocat"}


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
    """Vide les fichiers CSV candidates et verified."""
    for path in (_CANDIDATES_CSV, _VERIFIED_CSV):
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

            def log_callback(event: dict):
                if _stop_event.is_set():
                    raise InterruptedError("Agent stopped by user")
                loop.call_soon_threadsafe(queue.put_nowait, event)

            # Valider
            if request.role not in ROLES:
                yield _sse_event({"type": "error", "message": f"Role invalide: {request.role}"})
                return
            if request.specialty_num not in SPECIALTIES:
                yield _sse_event({"type": "error", "message": f"Spécialité invalide: {request.specialty_num}"})
                return

            role = ROLES[request.role]
            specialty = SPECIALTIES[request.specialty_num]

            parts = [
                f"Poste : {role}",
                f"Spécialité : {specialty['name_fr']} ({specialty['name_en']})",
                f"Ville : {request.location}",
            ]
            if request.extra:
                parts.append(f"Précisions : {request.extra}")
            user_query = "\n".join(parts)

            yield _sse_event({
                "type": "config",
                "role": role,
                "specialty": specialty["name_fr"],
                "location": request.location,
                "target_count": request.target_count,
            })

            logger.info(
                f"[AGENT] Lancement : {role} / {specialty['name_fr']} "
                f"/ {request.location} / {request.target_count}"
            )

            def run_in_thread():
                try:
                    from agent.graph import run_pipeline
                    run_pipeline(
                        user_query=user_query,
                        target_count=request.target_count,
                        company_size="",
                        specialty=specialty,
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
    return {
        "roles": ROLES,
        "specialties": {
            k: {"name_fr": v["name_fr"], "name_en": v["name_en"]}
            for k, v in SPECIALTIES.items()
        },
    }


@router.get("/csv/{csv_type}")
async def get_csv(csv_type: str):
    """Retourne le contenu actuel d'un CSV (candidates ou verified)."""
    if csv_type == "candidates":
        rows = _read_csv(_CANDIDATES_CSV)
    elif csv_type == "verified":
        rows = _read_csv(_VERIFIED_CSV)
    else:
        return {
            "error": f"Type CSV invalide: {csv_type}. "
            "Utilisez 'candidates' ou 'verified'."
        }
    return {"csv_type": csv_type, "count": len(rows), "rows": rows}
