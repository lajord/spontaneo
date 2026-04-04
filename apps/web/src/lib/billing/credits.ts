import { PrismaClient } from '@prisma/client'

type RawExecutor = Pick<PrismaClient, '$executeRaw'>

export async function consumeCreditsIfAvailable(
  db: RawExecutor,
  userId: string,
  credits: number,
): Promise<boolean> {
  const updatedRows = await db.$executeRaw`
    UPDATE "User"
    SET
      "credits" = "credits" - ${credits},
      "updatedAt" = NOW()
    WHERE id = ${userId}
      AND "credits" >= ${credits}
  `

  return Number(updatedRows) > 0
}
