import { NextRequest, NextResponse } from 'next/server'
import Stripe from 'stripe'
import { prisma } from '@/lib/prisma'
import { getStripe, getStripeWebhookSecret } from '@/lib/stripe'
import { parsePositiveInteger } from '@/lib/billing/config'
import {
  completeCreditPurchase,
  createCreditPurchase,
  expireCreditPurchase,
  findCreditPurchaseByCheckoutSessionId,
  findCreditPurchaseById,
} from '@/lib/billing/purchases'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
  const signature = req.headers.get('stripe-signature')
  if (!signature) {
    return NextResponse.json({ error: 'Signature Stripe absente' }, { status: 400 })
  }

  const payload = await req.text()

  let event: Stripe.Event
  try {
    event = getStripe().webhooks.constructEvent(payload, signature, getStripeWebhookSecret())
  } catch (error) {
    console.error('[stripe][webhook] invalid signature', error)
    return NextResponse.json({ error: 'Signature Stripe invalide' }, { status: 400 })
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed':
      case 'checkout.session.async_payment_succeeded':
        await handlePaidCheckoutSession(event.data.object as Stripe.Checkout.Session)
        break
      case 'checkout.session.expired':
        await markCheckoutSessionExpired(event.data.object as Stripe.Checkout.Session)
        break
      default:
        break
    }
  } catch (error) {
    console.error('[stripe][webhook] handler failed', error)
    return NextResponse.json({ error: 'Erreur webhook Stripe' }, { status: 500 })
  }

  return NextResponse.json({ received: true })
}

async function handlePaidCheckoutSession(session: Stripe.Checkout.Session): Promise<void> {
  if (session.payment_status !== 'paid') {
    return
  }

  const metadata = session.metadata ?? {}
  const paymentIntentId =
    typeof session.payment_intent === 'string'
      ? session.payment_intent
      : session.payment_intent?.id ?? null
  const customerId =
    typeof session.customer === 'string'
      ? session.customer
      : session.customer?.id ?? null

  await prisma.$transaction(async (tx) => {
    let purchase =
      (metadata.purchaseId
        ? await findCreditPurchaseById(tx, metadata.purchaseId)
        : null) ??
      await findCreditPurchaseByCheckoutSessionId(tx, session.id)

    if (!purchase) {
      const fallbackUserId = metadata.userId
      const fallbackCredits = parsePositiveInteger(metadata.credits)

      if (!fallbackUserId || !fallbackCredits) {
        throw new Error(`CreditPurchase introuvable pour la session ${session.id}`)
      }

      purchase = await createCreditPurchase(tx, {
        userId: fallbackUserId,
        campaignId: metadata.campaignId || null,
        credits: fallbackCredits,
        unitPriceCents: Math.max(1, Math.round((session.amount_total ?? fallbackCredits) / fallbackCredits)),
        amountCents: session.amount_total ?? 0,
        currency: (session.currency ?? 'eur').toLowerCase(),
        status: 'pending',
        stripeCheckoutSessionId: session.id,
        stripePaymentIntentId: paymentIntentId,
        stripeCustomerId: customerId,
      })
    }

    if (purchase.status === 'completed') {
      return
    }

    await tx.user.update({
      where: { id: purchase.userId },
      data: {
        credits: {
          increment: purchase.credits,
        },
      },
    })

    await completeCreditPurchase(tx, {
      id: purchase.id,
      checkoutSessionId: session.id,
      paymentIntentId,
      customerId,
      amountCents: session.amount_total ?? purchase.amountCents,
      currency: (session.currency ?? purchase.currency).toLowerCase(),
    })
  })
}

async function markCheckoutSessionExpired(session: Stripe.Checkout.Session): Promise<void> {
  const metadata = session.metadata ?? {}

  await expireCreditPurchase(prisma, {
    purchaseId: metadata.purchaseId,
    checkoutSessionId: session.id,
  })
}
