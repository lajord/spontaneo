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
  draft: 'bg-slate-100 text-slate-600 border-slate-200',
  scraped: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  emails_generated: 'bg-amber-50 text-amber-700 border-amber-200',
  sent: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  active: 'bg-brand-50 text-brand-700 border-brand-200',
  paused: 'bg-orange-50 text-orange-700 border-orange-200',
  finished: 'bg-slate-100 text-slate-600 border-slate-200',
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
    <div className="relative group h-full">
      <Link
        href={`/campaigns/${c.id}`}
        className="block h-full bg-white border border-slate-200 rounded-2xl p-6 hover:border-brand-300 hover:shadow-md hover:shadow-brand-500/5 transition-all duration-200"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <h2 className="font-semibold text-slate-900 text-base leading-tight group-hover:text-brand-600 transition-colors line-clamp-2">
            {c.name}
          </h2>
          <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md font-medium shrink-0 border ${STATUS_STYLES[c.status] ?? STATUS_STYLES.draft}`}>
            {c.status === 'active' && (
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            )}
            {STATUS_LABELS[c.status] ?? c.status}
          </span>
        </div>
        
        <p className="text-sm text-slate-500 mb-6 line-clamp-1 flex items-center gap-1.5">
          <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          {c.jobTitle} <span className="text-slate-300 mx-1">•</span> {c.location}
        </p>

        <div className="flex flex-wrap gap-3 text-sm text-slate-500 border-t border-slate-100 pt-4 mt-auto">
          <span className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-100">
            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
            </svg>
            <span className="font-medium text-slate-700">{c._count.companies}</span> entreprise{c._count.companies !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-100">
            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span className="font-medium text-slate-700">{c._count.emails}</span> mail{c._count.emails !== 1 ? 's' : ''}
          </span>
        </div>
      </Link>

      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={handleDeleteClick}
          disabled={deleting}
          className="w-8 h-8 rounded-lg bg-white border border-slate-200 text-slate-400 shadow-sm flex items-center justify-center hover:bg-red-50 hover:text-red-500 hover:border-red-200 transition-colors disabled:opacity-50"
          title="Supprimer la campagne"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      {confirmOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm"
          onClick={() => setConfirmOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl border border-slate-100 px-6 py-6 w-[340px] flex flex-col gap-5"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Supprimer la campagne ?</h3>
            </div>
            
            <p className="text-sm text-slate-500 leading-relaxed">
              Êtes-vous sûr de vouloir supprimer <span className="font-semibold text-slate-700">"{c.name}"</span> ? Cette action est irréversible et supprimera toutes les candidatures associées.
            </p>
            
            <div className="flex justify-end gap-3 mt-2">
              <button
                onClick={() => setConfirmOpen(false)}
                className="px-4 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg transition-colors"
                disabled={deleting}
              >
                Annuler
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors flex items-center justify-center gap-2"
                disabled={deleting}
              >
                {deleting ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Suppression...
                  </>
                ) : 'Oui, supprimer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
