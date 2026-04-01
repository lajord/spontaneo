from __future__ import annotations

import json

import asyncpg


async def append_job_event(conn: asyncpg.Connection, job_id: str, payload: dict) -> None:
    await conn.execute(
        """
        WITH locked_job AS (
            SELECT id
            FROM "Job"
            WHERE id = $1
            FOR UPDATE
        )
        INSERT INTO "JobEvent" ("id", "jobId", "seq", "payload", "createdAt")
        SELECT
            gen_random_uuid()::text,
            locked_job.id,
            COALESCE(MAX(evt.seq), 0) + 1,
            $2::jsonb,
            NOW()
        FROM locked_job
        LEFT JOIN "JobEvent" evt ON evt."jobId" = locked_job.id
        GROUP BY locked_job.id
        """,
        job_id,
        json.dumps(payload),
    )
