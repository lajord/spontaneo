import 'dotenv/config'
import { PrismaClient } from '@prisma/client'
import { PrismaPg } from '@prisma/adapter-pg'

function createPrismaClient() {
  const url = new URL(process.env.DATABASE_URL!)
  url.searchParams.delete('pgbouncer')
  url.searchParams.delete('sslmode')
  url.searchParams.delete('connection_limit')
  const adapter = new PrismaPg({
    connectionString: url.toString(),
    ssl: { rejectUnauthorized: false },
  })
  return new PrismaClient({ adapter })
}

const prisma = createPrismaClient()



/**
 * Appends anazd SSE event to the JobEvent table with a monotonically increasing seq per job.
 * Locks the parent job row so concurrent writers for the same job are serialized.
 */
export async function appendJobEvent(jobId: string, payload: object): Promise<void> {
  await prisma.$executeRaw`
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

export { prisma }
