'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import {
  CREDITS_PER_COMPANY,
  SCALE_PACK_AMOUNT_CENTS,
  SCALE_PACK_CREDITS,
  formatAmountCents,
} from '@/lib/billing/config'

type PricingClientProps = {
  currentCredits: number
  unitPriceCents: number
  currency: string
}

type OfferKey = 'payg' | 'scale'

const MIN_CREDITS = 20
const MAX_CREDITS = 300
const STEP_CREDITS = 10

export default function PricingClient({ currentCredits, unitPriceCents, currency }: PricingClientProps) {
  const router = useRouter()
  const [selectedOffer, setSelectedOffer] = useState<OfferKey>('payg')
  const [customCredits, setCustomCredits] = useState(60)
  const [error, setError] = useState('')
  const [isPending, startTransition] = useTransition()

  const credits = selectedOffer === 'scale' ? SCALE_PACK_CREDITS : customCredits
  const estimatedCompanies = Math.floor(credits / CREDITS_PER_COMPANY)
  const totalAmountCents =
    selectedOffer === 'scale' ? SCALE_PACK_AMOUNT_CENTS : credits * unitPriceCents

  function startCheckout() {
    setError('')

    startTransition(async () => {
      const res = await fetch('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credits }),
      })

      const data = await res.json().catch(() => ({ error: 'Erreur Stripe' }))

      if (res.status === 401) {
        router.push('/login')
        return
      }

      if (!res.ok || !data?.url) {
        setError(data.error ?? 'Impossible de lancer le checkout Stripe.')
        return
      }

      window.location.assign(data.url)
    })
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section className="overflow-hidden rounded-[30px] border border-[#d9e6de] bg-[linear-gradient(180deg,#fcfefc_0%,#f5faf6_100%)] shadow-[0_18px_50px_rgba(15,23,42,0.05)]">
        <div className="border-b border-[#e6efe9] px-8 py-8 sm:px-10">
          <p className="inline-flex rounded-full border border-[#dbe8e0] bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5d7568]">
            Pricing
          </p>
          <div className="mt-5 max-w-3xl">
            <h1 className="text-4xl font-semibold tracking-[-0.03em] text-slate-950 sm:text-[52px]">
              Une tarification claire,
              <br />
              pensee pour rester lisible.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
              Deux options seulement. Une formule flexible pour acheter au fil de l&apos;eau,
              et un pack 200 credits avec remise pour les campagnes plus intensives.
            </p>
          </div>
        </div>

        <div className="grid gap-4 px-8 py-8 sm:px-10 xl:grid-cols-2">
          <button
            type="button"
            onClick={() => setSelectedOffer('payg')}
            className={`rounded-[26px] border px-6 py-6 text-left transition ${
              selectedOffer === 'payg'
                ? 'border-[#9eb8a7] bg-white shadow-[0_16px_36px_rgba(123,156,135,0.12)]'
                : 'border-[#e2ebe5] bg-[#fbfdfb] hover:border-[#cadecf]'
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7a9685]">Offre 01</p>
                <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.03em] text-slate-950">Pay as you go</h2>
              </div>
              <span className="rounded-full border border-[#dbe7df] bg-[#f4f9f5] px-3 py-1 text-xs font-medium text-[#5d7568]">
                Flexible
              </span>
            </div>

            <div className="mt-8 flex items-end gap-3">
              <p className="text-5xl font-semibold tracking-[-0.04em] text-slate-950">{customCredits}</p>
              <p className="pb-2 text-sm uppercase tracking-[0.18em] text-slate-400">credits</p>
            </div>
            <p className="mt-2 text-sm text-slate-500">
              Soit environ {Math.floor(customCredits / CREDITS_PER_COMPANY)} entreprises.
            </p>

            <div className="mt-8 space-y-2 text-sm leading-6 text-slate-600">
              <p>Volume libre entre 20 et 300 credits.</p>
              <p>Parfait pour recharger progressivement.</p>
              <p>Paiement unique via Stripe Checkout.</p>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setSelectedOffer('scale')}
            className={`rounded-[26px] border px-6 py-6 text-left transition ${
              selectedOffer === 'scale'
                ? 'border-[#adc7b5] bg-[linear-gradient(180deg,#f6fbf7_0%,#edf6ef_100%)] shadow-[0_16px_36px_rgba(123,156,135,0.14)]'
                : 'border-[#e2ebe5] bg-white hover:border-[#cadecf]'
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7a9685]">Offre 02</p>
                <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.03em] text-slate-950">Pack 200 credits</h2>
              </div>
              <span className="rounded-full border border-[#dbe7df] bg-white px-3 py-1 text-xs font-medium text-[#5d7568]">
                -20%
              </span>
            </div>

            <div className="mt-8 flex items-end gap-3">
              <p className="text-5xl font-semibold tracking-[-0.04em] text-slate-950">{SCALE_PACK_CREDITS}</p>
              <p className="pb-2 text-sm uppercase tracking-[0.18em] text-slate-400">credits</p>
            </div>
            <p className="mt-2 text-sm text-slate-500">Soit environ 100 entreprises.</p>

            <div className="mt-8 space-y-2 text-sm leading-6 text-slate-600">
              <p>Remise de 20% appliquee sur le pack 200 credits.</p>
              <p>Le pack passe de 100 EUR a 80 EUR.</p>
              <p>Meme parcours de paiement, sans abonnement.</p>
            </div>
          </button>
        </div>

        <div className="border-t border-[#e6efe9] bg-white/70 px-8 py-8 sm:px-10">
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">Configuration</p>
              <div className="mt-2 flex items-end gap-3">
                <span className="text-5xl font-semibold tracking-[-0.04em] text-slate-950">{credits}</span>
                <span className="pb-2 text-sm text-slate-400">credits</span>
              </div>
            </div>

            <div className="rounded-[22px] border border-[#dfe9e3] bg-[#f7fbf8] px-5 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[#7a9685]">Equivalence</p>
              <p className="mt-1 text-lg font-semibold text-slate-950">{estimatedCompanies} entreprises</p>
            </div>
          </div>

          <div className={`mt-8 transition ${selectedOffer === 'payg' ? 'opacity-100' : 'opacity-35'}`}>
            <input
              type="range"
              min={MIN_CREDITS}
              max={MAX_CREDITS}
              step={STEP_CREDITS}
              value={customCredits}
              onChange={(event) => setCustomCredits(Number(event.target.value))}
              disabled={selectedOffer !== 'payg'}
              className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[#dce8e0] accent-[#6e907d] disabled:cursor-not-allowed"
            />
            <div className="mt-3 flex justify-between text-xs font-medium text-slate-400">
              <span>{MIN_CREDITS}</span>
              <span>{MAX_CREDITS}</span>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {[20, 50, 100, 150, 200].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  setSelectedOffer(value === SCALE_PACK_CREDITS ? 'scale' : 'payg')
                  setCustomCredits(value)
                }}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  credits === value
                    ? 'border border-[#6e907d] bg-[#eef6f0] text-[#466053]'
                    : 'border border-[#e3ebe6] bg-white text-slate-600 hover:border-[#ccdbd1] hover:bg-[#f8fbf9]'
                }`}
              >
                {value} credits
              </button>
            ))}
          </div>
        </div>
      </section>

      <aside className="rounded-[30px] border border-[#dce7e1] bg-white p-6 shadow-[0_18px_44px_rgba(15,23,42,0.05)]">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7a9685]">Synthese</p>
        <h2 className="mt-3 text-[30px] font-semibold tracking-[-0.03em] text-slate-950">Commande</h2>

        <div className="mt-8 rounded-[24px] border border-[#e4ece7] bg-[#fbfdfb] p-5">
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>Offre</span>
            <span className="font-medium text-slate-950">{selectedOffer === 'scale' ? 'Pack 200 credits' : 'Pay as you go'}</span>
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
            <span>Credits</span>
            <span className="font-medium text-slate-950">{credits}</span>
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
            <span>Entreprises couvertes</span>
            <span className="font-medium text-slate-950">{estimatedCompanies}</span>
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
            <span>Solde actuel</span>
            <span className="font-medium text-slate-950">{currentCredits}</span>
          </div>
        </div>

        <div className="mt-6 border-t border-slate-100 pt-6">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Total</p>
          <p className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-slate-950">
            {formatAmountCents(totalAmountCents, currency)}
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {selectedOffer === 'scale'
              ? `Pack 200 credits remisé : ${formatAmountCents(SCALE_PACK_AMOUNT_CENTS, currency)} au lieu de ${formatAmountCents(SCALE_PACK_CREDITS * unitPriceCents, currency)}.`
              : `Tarification a l'unite : ${formatAmountCents(unitPriceCents, currency)} par credit.`}
          </p>
        </div>

        <button
          type="button"
          onClick={startCheckout}
          disabled={isPending}
          className="mt-8 inline-flex w-full items-center justify-center rounded-[18px] border border-[#b7cbbd] bg-[#f4faf6] px-4 py-3 text-sm font-medium text-[#365245] transition hover:border-[#8fab98] hover:bg-[#ebf5ee] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? 'Redirection...' : 'Acheter des credits'}
        </button>

        {error && (
          <div className="mt-4 rounded-[18px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="mt-8 rounded-[24px] border border-[#e4ece7] bg-[linear-gradient(180deg,#fbfdfb_0%,#f5faf6_100%)] p-5 text-sm leading-6 text-slate-600">
          <p className="font-medium text-slate-950">Inclus</p>
          <p className="mt-2">
            Checkout Stripe heberge, paiement unique, creditage par webhook et utilisation immediate dans les campagnes.
          </p>
        </div>
      </aside>
    </div>
  )
}
