import { headers } from 'next/headers'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import PricingClient from './PricingClient'
import { getBillingCurrency, getCreditUnitPriceCents } from '@/lib/billing/config'

export default async function PricingPage() {
  const session = await auth.api.getSession({ headers: await headers() })

  const dbUser = session
    ? await prisma.user.findUnique({
        where: { id: session.user.id },
        select: { credits: true },
      })
    : null

  const unitPriceCents = getCreditUnitPriceCents()
  const currency = getBillingCurrency()

  return (
    <div className="min-h-full bg-[#f5f7f2] px-6 py-8">
      <div className="mx-auto max-w-6xl">
        <PricingClient
          currentCredits={dbUser?.credits ?? 0}
          unitPriceCents={unitPriceCents}
          currency={currency}
        />
      </div>
    </div>
  )
}
