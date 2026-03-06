import { PrismaClient } from '@prisma/client'
import { PrismaPg } from '@prisma/adapter-pg'
import { Pool } from 'pg'

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient }

function createPrismaClient() {
  // pg v8+ interprète sslmode=require comme verify-full — on strip les params
  // non-standard et on gère SSL manuellement
  const url = new URL(process.env.DATABASE_URL!)
  url.searchParams.delete('pgbouncer')
  url.searchParams.delete('sslmode')
  url.searchParams.delete('connection_limit')

  const pool = new Pool({
    connectionString: url.toString(),
    ssl: { rejectUnauthorized: false },
    family: 4,
  } as ConstructorParameters<typeof Pool>[0])
  const adapter = new PrismaPg(pool)
  return new PrismaClient({ adapter })
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient()

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma
