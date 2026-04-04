import { PrismaClient } from '@prisma/client'

type SqlExecutor = Pick<PrismaClient, '$queryRaw' | '$executeRaw'>

export type CreditPurchaseRecord = {
  id: string
  userId: string
  campaignId: string | null
  credits: number
  unitPriceCents: number
  amountCents: number
  currency: string
  status: string
  stripeCheckoutSessionId: string | null
  stripePaymentIntentId: string | null
  stripeCustomerId: string | null
  completedAt: Date | null
  createdAt: Date
  updatedAt: Date
}

type CreateCreditPurchaseInput = {
  userId: string
  campaignId: string | null
  credits: number
  unitPriceCents: number
  amountCents: number
  currency: string
  status: string
  stripeCheckoutSessionId?: string | null
  stripePaymentIntentId?: string | null
  stripeCustomerId?: string | null
}

export async function createCreditPurchase(
  db: SqlExecutor,
  input: CreateCreditPurchaseInput,
): Promise<CreditPurchaseRecord> {
  const rows = await db.$queryRaw<CreditPurchaseRecord[]>`
    INSERT INTO "CreditPurchase" (
      "id",
      "userId",
      "campaignId",
      "credits",
      "unitPriceCents",
      "amountCents",
      "currency",
      "status",
      "stripeCheckoutSessionId",
      "stripePaymentIntentId",
      "stripeCustomerId",
      "createdAt",
      "updatedAt"
    )
    VALUES (
      gen_random_uuid()::text,
      ${input.userId},
      ${input.campaignId},
      ${input.credits},
      ${input.unitPriceCents},
      ${input.amountCents},
      ${input.currency},
      ${input.status},
      ${input.stripeCheckoutSessionId ?? null},
      ${input.stripePaymentIntentId ?? null},
      ${input.stripeCustomerId ?? null},
      NOW(),
      NOW()
    )
    RETURNING
      "id",
      "userId",
      "campaignId",
      "credits",
      "unitPriceCents",
      "amountCents",
      "currency",
      "status",
      "stripeCheckoutSessionId",
      "stripePaymentIntentId",
      "stripeCustomerId",
      "completedAt",
      "createdAt",
      "updatedAt"
  `

  if (!rows[0]) {
    throw new Error('Impossible de creer le CreditPurchase.')
  }

  return rows[0]
}

export async function findCreditPurchaseById(
  db: SqlExecutor,
  id: string,
): Promise<CreditPurchaseRecord | null> {
  const rows = await db.$queryRaw<CreditPurchaseRecord[]>`
    SELECT
      "id",
      "userId",
      "campaignId",
      "credits",
      "unitPriceCents",
      "amountCents",
      "currency",
      "status",
      "stripeCheckoutSessionId",
      "stripePaymentIntentId",
      "stripeCustomerId",
      "completedAt",
      "createdAt",
      "updatedAt"
    FROM "CreditPurchase"
    WHERE "id" = ${id}
    LIMIT 1
  `

  return rows[0] ?? null
}

export async function findCreditPurchaseByCheckoutSessionId(
  db: SqlExecutor,
  checkoutSessionId: string,
): Promise<CreditPurchaseRecord | null> {
  const rows = await db.$queryRaw<CreditPurchaseRecord[]>`
    SELECT
      "id",
      "userId",
      "campaignId",
      "credits",
      "unitPriceCents",
      "amountCents",
      "currency",
      "status",
      "stripeCheckoutSessionId",
      "stripePaymentIntentId",
      "stripeCustomerId",
      "completedAt",
      "createdAt",
      "updatedAt"
    FROM "CreditPurchase"
    WHERE "stripeCheckoutSessionId" = ${checkoutSessionId}
    LIMIT 1
  `

  return rows[0] ?? null
}

export async function setCreditPurchaseCheckoutSessionId(
  db: SqlExecutor,
  id: string,
  checkoutSessionId: string,
): Promise<void> {
  await db.$executeRaw`
    UPDATE "CreditPurchase"
    SET
      "stripeCheckoutSessionId" = ${checkoutSessionId},
      "updatedAt" = NOW()
    WHERE "id" = ${id}
  `
}

export async function markCreditPurchaseFailed(
  db: SqlExecutor,
  id: string,
): Promise<void> {
  await db.$executeRaw`
    UPDATE "CreditPurchase"
    SET
      "status" = 'failed',
      "updatedAt" = NOW()
    WHERE "id" = ${id}
  `
}

export async function completeCreditPurchase(
  db: SqlExecutor,
  input: {
    id: string
    checkoutSessionId: string
    paymentIntentId: string | null
    customerId: string | null
    amountCents: number
    currency: string
  },
): Promise<void> {
  await db.$executeRaw`
    UPDATE "CreditPurchase"
    SET
      "status" = 'completed',
      "stripeCheckoutSessionId" = ${input.checkoutSessionId},
      "stripePaymentIntentId" = ${input.paymentIntentId},
      "stripeCustomerId" = ${input.customerId},
      "amountCents" = ${input.amountCents},
      "currency" = ${input.currency},
      "completedAt" = NOW(),
      "updatedAt" = NOW()
    WHERE "id" = ${input.id}
  `
}

export async function expireCreditPurchase(
  db: SqlExecutor,
  input: {
    purchaseId?: string
    checkoutSessionId: string
  },
): Promise<void> {
  if (input.purchaseId) {
    await db.$executeRaw`
      UPDATE "CreditPurchase"
      SET
        "status" = 'expired',
        "stripeCheckoutSessionId" = COALESCE("stripeCheckoutSessionId", ${input.checkoutSessionId}),
        "updatedAt" = NOW()
      WHERE "status" = 'pending'
        AND (
          "id" = ${input.purchaseId}
          OR "stripeCheckoutSessionId" = ${input.checkoutSessionId}
        )
    `
    return
  }

  await db.$executeRaw`
    UPDATE "CreditPurchase"
    SET
      "status" = 'expired',
      "updatedAt" = NOW()
    WHERE "status" = 'pending'
      AND "stripeCheckoutSessionId" = ${input.checkoutSessionId}
  `
}
