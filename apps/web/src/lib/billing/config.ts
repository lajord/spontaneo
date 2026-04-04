export const CREDITS_PER_COMPANY = 2
export const MAX_CREDIT_PURCHASE = 5000
export const DEFAULT_CREDIT_PRICE_CENTS = 50
export const SCALE_PACK_CREDITS = 200
export const SCALE_PACK_AMOUNT_CENTS = 8000

export function parsePositiveInteger(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) {
    return value
  }

  if (typeof value === 'string' && /^\d+$/.test(value)) {
    const parsed = Number.parseInt(value, 10)
    return parsed > 0 ? parsed : null
  }

  return null
}

export function computeCreditsForCompanyCount(companyCount: number): number {
  return companyCount * CREDITS_PER_COMPANY
}

export function getBillingCurrency(): string {
  return (process.env.STRIPE_CURRENCY ?? 'eur').toLowerCase()
}

export function getCreditUnitPriceCents(): number {
  const raw = process.env.STRIPE_CREDIT_PRICE_CENTS
  const parsed = parsePositiveInteger(raw)

  return parsed ?? DEFAULT_CREDIT_PRICE_CENTS
}

export function quoteCreditPurchase(credits: number): {
  credits: number
  unitPriceCents: number
  amountCents: number
  currency: string
} {
  const normalizedCredits = parsePositiveInteger(credits)

  if (!normalizedCredits || normalizedCredits > MAX_CREDIT_PURCHASE) {
    throw new Error('Nombre de credits invalide pour un checkout Stripe.')
  }

  const unitPriceCents =
    normalizedCredits === SCALE_PACK_CREDITS
      ? Math.floor(SCALE_PACK_AMOUNT_CENTS / SCALE_PACK_CREDITS)
      : getCreditUnitPriceCents()

  return {
    credits: normalizedCredits,
    unitPriceCents,
    amountCents: normalizedCredits * unitPriceCents,
    currency: getBillingCurrency(),
  }
}

export function formatAmountCents(amountCents: number, currency: string): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(amountCents / 100)
}
