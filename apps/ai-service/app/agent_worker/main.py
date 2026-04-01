from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from app.agent_worker.job_store import claim_next_agent_job, create_pool, recover_stale_jobs
from app.agent_worker.runner import run_agent_job
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("agent-worker")

MAX_CONCURRENT = int(os.getenv("AGENT_WORKER_MAX_CONCURRENT", "2"))
POLL_INTERVAL_MS = int(os.getenv("AGENT_WORKER_POLL_INTERVAL_MS", "5000"))
STALE_THRESHOLD_SECONDS = int(os.getenv("AGENT_WORKER_STALE_THRESHOLD_SECONDS", "3600"))


def _log_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.info("[agent-worker] Task cancelled")
    except Exception:
        logger.exception("[agent-worker] Background task crashed")


async def worker_loop() -> None:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquant pour agent-worker")

    pool = await create_pool(settings.DATABASE_URL)
    active_tasks: set[asyncio.Task] = set()

    try:
        recovered = await recover_stale_jobs(pool, STALE_THRESHOLD_SECONDS)
        if recovered > 0:
            logger.info("[agent-worker] Reset %s stale job(s) to pending", recovered)

        while True:
            active_tasks = {task for task in active_tasks if not task.done()}

            while len(active_tasks) < MAX_CONCURRENT:
                job = await claim_next_agent_job(pool)
                if not job:
                    break

                logger.info("[agent-worker] Starting job %s for campaign %s", job.id, job.campaign_id)
                task = asyncio.create_task(run_agent_job(pool, job))
                task.add_done_callback(_log_task_result)
                active_tasks.add(task)

            await asyncio.sleep(POLL_INTERVAL_MS / 1000)
    finally:
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        await pool.close()


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
