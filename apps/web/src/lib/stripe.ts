import Stripe from 'stripe'

let stripeClient: Stripe | null = null

export function getStripe(): Stripe {
  const secretKey = process.env.STRIPE_SECRET_KEY
  if (!secretKey) {
    throw new Error('STRIPE_SECRET_KEY est manquant.')
  }

  if (!stripeClient) {
    stripeClient = new Stripe(secretKey, {
      // Le SDK installe peut avoir un retard de typage sur la derniere version d'API.
      apiVersion: '2026-02-25.clover' as any,
    })
  }

  return stripeClient
}

export function getStripeWebhookSecret(): string {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET
  if (!webhookSecret) {
    throw new Error('STRIPE_WEBHOOK_SECRET est manquant.')
  }

  return webhookSecret
}
