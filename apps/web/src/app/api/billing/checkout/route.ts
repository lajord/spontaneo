import { NextRequest, NextResponse } from 'next/server'
import { headers } from 'next/headers'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { getStripe } from '@/lib/stripe'
import { getAppUrl } from '@/lib/app-url'
import { parsePositiveInteger, quoteCreditPurchase } from '@/lib/billing/config'
import {
  createCreditPurchase,
  markCreditPurchaseFailed,
  setCreditPurchaseCheckoutSessionId,
} from '@/lib/billing/purchases'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) {
    return NextResponse.json({ error: 'Non autorise' }, { status: 401 })
  }

  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Payload invalide' }, { status: 400 })
  }

  const rawCredits = typeof body === 'object' && body !== null ? (body as { credits?: unknown }).credits : null
  const rawCampaignId = typeof body === 'object' && body !== null ? (body as { campaignId?: unknown }).campaignId : null

  const credits = parsePositiveInteger(rawCredits)
  const campaignId = typeof rawCampaignId === 'string' && rawCampaignId.trim() !== '' ? rawCampaignId : null

  if (!credits) {
    return NextResponse.json({ error: 'Nombre de credits invalide' }, { status: 400 })
  }

  if (campaignId) {
    const campaign = await prisma.campaign.findFirst({
      where: { id: campaignId, userId: session.user.id },
      select: { id: true },
    })

    if (!campaign) {
      return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })
    }
  }

  let quote: ReturnType<typeof quoteCreditPurchase>
  try {
    quote = quoteCreditPurchase(credits)
  } catch (error) {
    console.error('[stripe][checkout] invalid billing config', error)
    return NextResponse.json(
      { error: 'Configuration Stripe invalide. Verifiez STRIPE_CREDIT_PRICE_CENTS.' },
      { status: 500 },
    )
  }

  const purchase = await createCreditPurchase(prisma, {
    userId: session.user.id,
    campaignId,
    credits: quote.credits,
    unitPriceCents: quote.unitPriceCents,
    amountCents: quote.amountCents,
    currency: quote.currency,
    status: 'pending',
  })

  try {
    const stripe = getStripe()
    const appUrl = getAppUrl(req.nextUrl.origin)
    const successUrl = new URL('/billing/success', appUrl)
    successUrl.searchParams.set('session_id', '{CHECKOUT_SESSION_ID}')
    if (campaignId) {
      successUrl.searchParams.set('campaignId', campaignId)
    }

    const cancelUrl = new URL(campaignId ? `/campaigns/${campaignId}` : '/dashboard', appUrl)

    const checkoutSession = await stripe.checkout.sessions.create({
      mode: 'payment',
      success_url: successUrl.toString(),
      cancel_url: cancelUrl.toString(),
      customer_email: session.user.email,
      client_reference_id: session.user.id,
      line_items: [
        {
          quantity: quote.credits,
          price_data: {
            currency: quote.currency,
            unit_amount: quote.unitPriceCents,
            product_data: {
              name: 'Credit Spontaneo',
              description: 'Achat unique de credits pour lancer vos campagnes.',
            },
          },
        },
      ],
      metadata: {
        purchaseId: purchase.id,
        userId: session.user.id,
        campaignId: campaignId ?? '',
        credits: String(quote.credits),
      },
      payment_intent_data: {
        metadata: {
          purchaseId: purchase.id,
          userId: session.user.id,
          campaignId: campaignId ?? '',
          credits: String(quote.credits),
        },
      },
      locale: 'fr',
    })

    if (!checkoutSession.url) {
      throw new Error("Stripe n'a pas retourne d'URL de checkout.")
    }

    await setCreditPurchaseCheckoutSessionId(prisma, purchase.id, checkoutSession.id)

    return NextResponse.json({ url: checkoutSession.url })
  } catch (error) {
    await markCreditPurchaseFailed(prisma, purchase.id).catch(() => undefined)

    console.error('[stripe][checkout] creation session failed', error)
    return NextResponse.json(
      { error: 'Impossible de creer la session de paiement Stripe.' },
      { status: 500 },
    )
  }
}
