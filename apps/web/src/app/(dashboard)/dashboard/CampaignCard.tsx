'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

const STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  scraped: 'Scrapé',
  emails_generated: 'Mails générés',
  sent: 'Envoyé',
  active: 'En cours',
  paused: 'En pause',
  finished: 'Terminée',
}

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-500',
  scraped: 'bg-brand-50 text-brand-600',
  emails_generated: 'bg-amber-50 text-amber-600',
  sent: 'bg-emerald-50 text-emerald-600',
  active: 'bg-emerald-50 text-emerald-700',
  paused: 'bg-amber-50 text-amber-600',
  finished: 'bg-slate-100 text-slate-500',
}

interface Props {
  campaign: {
    id: string
    name: string
    status: string
    jobTitle: string
    location: string
    _count: { companies: number; emails: number }
  }
}

export default function CampaignCard({ campaign: c }: Props) {
  const router = useRouter()
  const [deleting, setDeleting] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)

  function handleDeleteClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    setConfirmOpen(true)
  }

  async function confirmDelete() {
    setConfirmOpen(false)
    setDeleting(true)
    await fetch(`/api/campaigns/${c.id}`, { method: 'DELETE' })
    router.refresh()
  }

  return (
    <div className="relative group">
      <Link
        href={`/campaigns/${c.id}`}
        className="block bg-white border border-slate-100 rounded-xl p-5 hover:border-brand-200 hover:shadow-sm transition-all"
      >
        <div className="flex items-start justify-between gap-2 mb-3">
          <h2 className="font-semibold text-slate-900 text-sm leading-tight group-hover:text-brand-600 transition-colors">
            {c.name}
          </h2>
          <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${STATUS_STYLES[c.status] ?? STATUS_STYLES.draft}`}>
            {c.status === 'active' && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            )}
            {STATUS_LABELS[c.status] ?? c.status}
          </span>
        </div>
        <p className="text-xs text-slate-400 mb-4 truncate">{c.jobTitle} · {c.location}</p>
        <div className="flex gap-4 text-xs text-slate-400 border-t border-slate-50 pt-3 mt-auto">
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
            </svg>
            {c._count.companies} entreprise{c._count.companies !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            {c._count.emails} mail{c._count.emails !== 1 ? 's' : ''}
          </span>
        </div>
      </Link>

      {/* Bouton suppression au hover */}
      <button
        onClick={handleDeleteClick}
        disabled={deleting}
        className="absolute top-2.5 right-2.5 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 disabled:opacity-50"
        title="Supprimer la campagne"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Modal de confirmation */}
      {confirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setConfirmOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-lg px-6 py-5 w-80 flex flex-col gap-4"
            onClick={e => e.stopPropagation()}
          >
            <p className="text-sm font-medium text-slate-800">
              Supprimer <span className="font-semibold">"{c.name}"</span> ?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmOpen(false)}
                className="px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={confirmDelete}
                className="px-3 py-1.5 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
