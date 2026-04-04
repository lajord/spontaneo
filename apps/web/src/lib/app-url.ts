export function getAppUrl(fallbackOrigin?: string): string {
  const candidate =
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.BETTER_AUTH_URL ??
    fallbackOrigin

  if (!candidate) {
    throw new Error('NEXT_PUBLIC_APP_URL ou BETTER_AUTH_URL est requis pour Stripe.')
  }

  return candidate.replace(/\/$/, '')
}
