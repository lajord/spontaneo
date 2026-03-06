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
 * Appends an SSE event to the JobEvent table with a monotonically increasing seq per job.
 * Uses a subquery INSERT to compute the next seq atomically.
 */
export async function appendJobEvent(jobId: string, payload: object): Promise<void> {
  await prisma.$executeRaw`
    INSERT INTO "JobEvent" ("id", "jobId", "seq", "payload", "createdAt")
    VALUES (
      gen_random_uuid()::text,
      ${jobId},
      (SELECT COALESCE(MAX(seq), 0) + 1 FROM "JobEvent" WHERE "jobId" = ${jobId}),
      ${JSON.stringify(payload)}::jsonb,
      NOW()
    )
  `
}

export { prisma }
