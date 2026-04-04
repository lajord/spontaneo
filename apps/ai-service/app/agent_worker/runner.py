from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import math
import os
import sys
import threading
from typing import Any

import asyncpg
import requests as http_requests

from app.agent_worker.event_store import append_job_event
from app.agent_worker.job_store import AgentJob, is_cancel_requested, mark_cancelled, mark_completed, mark_failed

logger = logging.getLogger(__name__)

_DOCKER_PKG = os.path.normpath(os.path.join("/app", "agent"))
_APPS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_LOCAL_PKG = os.path.join(_APPS_DIR, "agent")
_AGENT_PKG = _DOCKER_PKG if os.path.isdir(_DOCKER_PKG) else _LOCAL_PKG

if _AGENT_PKG not in sys.path:
    sys.path.insert(0, _AGENT_PKG)

from pipeline.graph import run_pipeline
from runtime import set_cancel_checker

SECTEUR_TO_VERTICAL = {
    "cabinet_avocat": "cabinets",
    "banque": "banques",
    "fond_investissement": "fonds",
}
CREDITS_PER_COMPANY = 2
DEFAULT_AGENT_TARGET_COUNT = 10
WORKER_URL = os.getenv("WORKER_URL", "http://worker:3001")
WORKER_SECRET = os.getenv("WORKER_SECRET", "")


async def create_campaign_generate_job(
    pool: asyncpg.Pool,
    user_id: str,
    campaign_id: str,
    generate_config: dict[str, Any],
) -> str | None:
    """Create a campaign_generate job so the Worker can generate mails/LM."""
    try:
        async with pool.acquire() as conn:
            job_id = await conn.fetchval(
                """
                INSERT INTO "Job" (id, "userId", "campaignId", type, status, payload, "createdAt", "updatedAt")
                VALUES (gen_random_uuid()::text, $1, $2, 'campaign_generate', 'pending', $3::jsonb, NOW(), NOW())
                RETURNING id
                """,
                user_id,
                campaign_id,
                json.dumps(generate_config),
            )
        logger.info("[agent-worker] Created campaign_generate job %s for campaign %s", job_id, campaign_id)

        # Nudge the Worker so it picks up the job immediately
        try:
            headers = {}
            if WORKER_SECRET:
                headers["x-worker-secret"] = WORKER_SECRET
            http_requests.post(f"{WORKER_URL}/nudge", headers=headers, timeout=5)
        except Exception:
            pass  # Worker will poll eventually

        return job_id
    except Exception:
        logger.exception("[agent-worker] Failed to create campaign_generate job for campaign %s", campaign_id)
        return None


async def update_campaign_status(pool: asyncpg.Pool, campaign_id: str | None, status: str) -> None:
    if not campaign_id:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "Campaign"
            SET status = $2,
                "updatedAt" = NOW()
            WHERE id = $1
            """,
            campaign_id,
            status,
        )


def _summarize_event_for_log(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "event")
    if event_type == "phase":
        return f"[PHASE] {event.get('name', '')} - {event.get('message', '')}"
    if event_type == "progress":
        return f"[PROGRESS] {event.get('message', '')}"
    if event_type == "tool_call":
        return f"[TOOL] {event.get('name', '')}({str(event.get('args', ''))[:300]})"
    if event_type == "tool_result":
        return f"[RESULT] {str(event.get('message', ''))[:500]}"
    if event_type == "error":
        return f"[ERROR] {event.get('message', '')}"
    if event_type == "config":
        return (
            f"[CONFIG] {event.get('secteur', '')} / {event.get('sous_secteur', '')} / "
            f"{event.get('job_title', '')} / {event.get('location', '')}"
        )
    if event_type == "complete":
        return "[COMPLETE] Pipeline termine"
    if event_type == "cancelled":
        return f"[CANCELLED] {event.get('message', '')}"
    return f"[{event_type.upper()}] {str(event.get('message', ''))[:500]}"


def resolve_target_count(payload: dict[str, Any]) -> int:
    credit_budget = payload.get("creditBudget")
    if isinstance(credit_budget, int) and credit_budget > 0:
        return max(1, math.floor(credit_budget / CREDITS_PER_COMPANY))
    target_count = payload.get("targetCount")
    if isinstance(target_count, int) and target_count > 0:
        return target_count
    return DEFAULT_AGENT_TARGET_COUNT


def build_user_query(payload: dict[str, Any], secteur_label: str) -> str:
    parts = [
        f"Poste vise : {payload.get('jobTitle', '')}",
        f"Secteur : {secteur_label}",
        f"Ville : {payload.get('location', '')}",
    ]
    sous_secteur = payload.get("sousSecteur")
    if sous_secteur:
        parts.append(f"Sous-secteur : {sous_secteur}")
    extra = payload.get("extra")
    if extra:
        parts.append(f"Precisions : {extra}")
    return "\n".join(parts)


async def run_agent_job(pool: asyncpg.Pool, job: AgentJob) -> None:
    payload = job.payload or {}
    secteur = str(payload.get("secteur") or "")
    mode = str(payload.get("mode") or "full")
    vertical_id = SECTEUR_TO_VERTICAL.get(secteur)
    if not vertical_id:
        await mark_failed(pool, job.id, f"Secteur inconnu: {secteur}")
        return

    secteur_label = {
        "cabinet_avocat": "Cabinet Avocat",
        "banque": "Banque",
        "fond_investissement": "Fond d'investissement",
    }.get(secteur, secteur)
    target_count = resolve_target_count(payload)
    user_query = build_user_query(payload, secteur_label)

    loop = asyncio.get_running_loop()
    stop_event = threading.Event()
    pending_writes: set[concurrent.futures.Future] = set()
    watcher_task: asyncio.Task | None = None

    def track_future(fut: concurrent.futures.Future) -> None:
        pending_writes.add(fut)
        def _on_done(done: concurrent.futures.Future) -> None:
            pending_writes.discard(done)
            try:
                done.result()
            except Exception:
                logger.exception("[agent-worker] Job %s failed while persisting event", job.id)
        fut.add_done_callback(_on_done)

    async def emit(payload_event: dict) -> None:
        async with pool.acquire() as conn:
            await append_job_event(conn, job.id, payload_event)

    def log_callback(event: dict) -> None:
        if stop_event.is_set():
            raise InterruptedError("Agent stopped by user")
        logger.info("[agent-worker][job:%s] %s", job.id, _summarize_event_for_log(event))
        fut = asyncio.run_coroutine_threadsafe(emit(event), loop)
        track_future(fut)

    async def cancel_watcher() -> None:
        try:
            while True:
                if await is_cancel_requested(pool, job.id):
                    stop_event.set()
                    return
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return

    def run_sync() -> None:
        logger.info("[agent-worker] Job %s entering run_pipeline", job.id)
        set_cancel_checker(stop_event.is_set)
        run_pipeline(
            secteur=vertical_id,
            query=user_query,
            job_title=str(payload.get("jobTitle") or ""),
            target_count=target_count,
            log_callback=log_callback,
            user_id=job.user_id,
            job_id=job.id,
            campaign_id=job.campaign_id,
            location=str(payload.get("location") or ""),
            mode=mode,
        )
        logger.info("[agent-worker] Job %s run_pipeline completed", job.id)

    try:
        logger.info("[agent-worker] Job %s writing initial config event", job.id)
        async with pool.acquire() as conn:
            await append_job_event(conn, job.id, {
                "type": "config",
                "secteur": secteur_label,
                "sous_secteur": payload.get("sousSecteur", ""),
                "job_title": payload.get("jobTitle", ""),
                "location": payload.get("location", ""),
                "credit_budget": payload.get("creditBudget"),
                "target_count": target_count,
                "campaign_id": job.campaign_id,
                "job_id": job.id,
            })

        watcher_task = asyncio.create_task(cancel_watcher())
        await loop.run_in_executor(None, run_sync)

        if stop_event.is_set() or await is_cancel_requested(pool, job.id):
            logger.info("[agent-worker] Job %s marked cancelled after pipeline stop", job.id)
            async with pool.acquire() as conn:
                await append_job_event(conn, job.id, {"type": "cancelled", "message": "Job agent annule"})
            if mode == "collect":
                await update_campaign_status(pool, job.campaign_id, "draft")
            elif mode == "enrich":
                await update_campaign_status(pool, job.campaign_id, "scraped")
            await mark_cancelled(pool, job.id)
            return

        if mode == "collect":
            await update_campaign_status(pool, job.campaign_id, "scraped")
        elif mode == "enrich" and job.campaign_id:
            # Enrichment done — chain to campaign_generate for mail/LM generation
            await update_campaign_status(pool, job.campaign_id, "generating")
            gen_config = payload.get("generateConfig", {})
            await create_campaign_generate_job(pool, job.user_id, job.campaign_id, gen_config)

        async with pool.acquire() as conn:
            await append_job_event(conn, job.id, {"type": "complete"})
        await mark_completed(pool, job.id)
        logger.info("[agent-worker] Job %s marked completed", job.id)
    except InterruptedError:
        logger.info("[agent-worker] Job %s interrupted by stop request", job.id)
        async with pool.acquire() as conn:
            await append_job_event(conn, job.id, {"type": "cancelled", "message": "Job agent annule"})
        if mode == "collect":
            await update_campaign_status(pool, job.campaign_id, "draft")
        await mark_cancelled(pool, job.id)
    except Exception as exc:
        logger.exception("[agent-worker] Job %s failed", job.id)
        try:
            async with pool.acquire() as conn:
                await append_job_event(conn, job.id, {"type": "error", "message": str(exc)})
        except Exception:
            logger.exception("[agent-worker] Job %s failed while writing error event", job.id)
        if mode == "collect":
            try:
                await update_campaign_status(pool, job.campaign_id, "draft")
            except Exception:
                logger.exception("[agent-worker] Job %s failed while resetting campaign status", job.id)
        try:
            await mark_failed(pool, job.id, str(exc))
        except Exception:
            logger.exception("[agent-worker] Job %s failed while marking failed", job.id)
    finally:
        stop_event.set()
        if watcher_task is not None:
            watcher_task.cancel()
            try:
                await watcher_task
            except asyncio.CancelledError:
                pass
        if pending_writes:
            await asyncio.gather(
                *(asyncio.wrap_future(future) for future in list(pending_writes)),
                return_exceptions=True,
            )
