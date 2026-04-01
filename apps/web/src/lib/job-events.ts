import { PrismaClient } from '@prisma/client'

type RawExecutor = Pick<PrismaClient, '$executeRaw'>

export async function appendJobEvent(db: RawExecutor, jobId: string, payload: object): Promise<void> {
  await db.$executeRaw`
    WITH locked_job AS (
      SELECT id
      FROM "Job"
      WHERE id = ${jobId}
      FOR UPDATE
    )
    INSERT INTO "JobEvent" ("id", "jobId", "seq", "payload", "createdAt")
    SELECT
      gen_random_uuid()::text,
      locked_job.id,
      COALESCE(MAX(evt.seq), 0) + 1,
      ${JSON.stringify(payload)}::jsonb,
      NOW()
    FROM locked_job
    LEFT JOIN "JobEvent" evt ON evt."jobId" = locked_job.id
    GROUP BY locked_job.id
  `
}
