import Link from 'next/link'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'
import { getStripe } from '@/lib/stripe'
import { formatAmountCents, parsePositiveInteger } from '@/lib/billing/config'

type BillingSuccessPageProps = {
  searchParams?: {
    session_id?: string
    campaignId?: string
  }
}

export default async function BillingSuccessPage({ searchParams }: BillingSuccessPageProps) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) {
    redirect('/login')
  }

  const sessionId = typeof searchParams?.session_id === 'string' ? searchParams.session_id : null
  const campaignId = typeof searchParams?.campaignId === 'string' ? searchParams.campaignId : null

  let purchasedCredits: number | null = null
  let paidAmountLabel: string | null = null
  let paymentConfirmed = false

  if (sessionId) {
    try {
      const checkoutSession = await getStripe().checkout.sessions.retrieve(sessionId)
      if (checkoutSession.client_reference_id === session.user.id) {
        purchasedCredits = parsePositiveInteger(checkoutSession.metadata?.credits)
        if (typeof checkoutSession.amount_total === 'number' && checkoutSession.currency) {
          paidAmountLabel = formatAmountCents(checkoutSession.amount_total, checkoutSession.currency)
        }
        paymentConfirmed = checkoutSession.payment_status === 'paid'
      }
    } catch (error) {
      console.error('[stripe][success-page] unable to retrieve checkout session', error)
    }
  }

  const returnHref = campaignId ? `/campaigns/${campaignId}` : '/dashboard'

  return (
    <div className="min-h-[calc(100vh-6rem)] flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
          <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 className="text-2xl font-semibold text-slate-900">Paiement pris en compte</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {paymentConfirmed
            ? 'Les credits ont ete ajoutes a votre compte. Vous pouvez reprendre votre campagne.'
            : "La page a bien ete atteinte, mais Stripe n'a pas encore confirme le paiement. Le webhook finalisera le creditage des que le paiement sera valide."}
        </p>

        {(purchasedCredits || paidAmountLabel) && (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-700">
            {purchasedCredits && <p>{purchasedCredits} credits achetes</p>}
            {paidAmountLabel && <p className="mt-1">Montant paye : {paidAmountLabel}</p>}
          </div>
        )}

        <div className="mt-8 flex items-center gap-3">
          <Link
            href={returnHref}
            className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            Revenir a la campagne
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Aller au dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}
