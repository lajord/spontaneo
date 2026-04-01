from __future__ import annotations

import json
from dataclasses import dataclass

import asyncpg


@dataclass(slots=True)
class AgentJob:
    id: str
    user_id: str
    campaign_id: str | None
    payload: dict


def _normalize_payload(raw_payload: object) -> dict:
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10)


async def recover_stale_jobs(pool: asyncpg.Pool, stale_after_seconds: int) -> int:
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE "Job"
            SET status = 'pending',
                "startedAt" = NULL,
                "updatedAt" = NOW()
            WHERE type = 'agent_search'
              AND status = 'running'
              AND "startedAt" < (NOW() - ($1 * INTERVAL '1 second'))
            """,
            stale_after_seconds,
        )
    return int(result.split()[-1])


async def claim_next_agent_job(pool: asyncpg.Pool) -> AgentJob | None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                WITH next_job AS (
                    SELECT id
                    FROM "Job"
                    WHERE type = 'agent_search'
                      AND status = 'pending'
                    ORDER BY "createdAt" ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE "Job" j
                SET status = 'running',
                    "startedAt" = NOW(),
                    "updatedAt" = NOW()
                FROM next_job
                WHERE j.id = next_job.id
                RETURNING j.id, j."userId", j."campaignId", j.payload
                """,
            )

    if not row:
        return None

    return AgentJob(
        id=row["id"],
        user_id=row["userId"],
        campaign_id=row["campaignId"],
        payload=_normalize_payload(row["payload"]),
    )


async def is_cancel_requested(pool: asyncpg.Pool, job_id: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, "cancelRequestedAt"
            FROM "Job"
            WHERE id = $1
            """,
            job_id,
        )
    if not row:
        return True
    return row["status"] == "cancelled" or row["cancelRequestedAt"] is not None


async def mark_completed(pool: asyncpg.Pool, job_id: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "Job"
            SET status = 'completed',
                error = NULL,
                "completedAt" = NOW(),
                "updatedAt" = NOW()
            WHERE id = $1
            """,
            job_id,
        )


async def mark_cancelled(pool: asyncpg.Pool, job_id: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "Job"
            SET status = 'cancelled',
                "completedAt" = NOW(),
                "updatedAt" = NOW()
            WHERE id = $1
            """,
            job_id,
        )


async def mark_failed(pool: asyncpg.Pool, job_id: str, error: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "Job"
            SET status = 'failed',
                error = $2,
                "completedAt" = NOW(),
                "updatedAt" = NOW()
            WHERE id = $1
            """,
            job_id,
            error,
        )
