'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

type Email = {
  id: string
  subject: string
  body: string
  status: string
  sentAt: string | null
  company: {
    id: string
    name: string
    website: string | null
  }
}

export default function EmailsPage({ params }: { params: { id: string } }) {
  const { id } = params
  const [emails, setEmails] = useState<Email[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetch(`/api/campaigns/${id}/emails`)
      .then((r) => r.json())
      .then((data) => {
        setEmails(Array.isArray(data) ? data : [])
        setLoading(false)
      })
  }, [id])

  async function sendEmail(emailId: string) {
    setSending(emailId)
    setMessage('')
    const res = await fetch(`/api/emails/${emailId}/send`, { method: 'POST' })
    const data = await res.json()

    if (res.ok) {
      setEmails((prev) =>
        prev.map((e) => (e.id === emailId ? { ...e, status: 'sent', sentAt: new Date().toISOString() } : e))
      )
      setMessage('Mail envoyé')
    } else {
      setMessage(data.error ?? "Erreur d'envoi")
    }
    setSending(null)
  }

  async function sendAll() {
    const drafts = emails.filter((e) => e.status === 'draft')
    for (const email of drafts) {
      await sendEmail(email.id)
    }
  }

  if (loading) return <div className="p-8 text-sm text-gray-400">Chargement...</div>

  const draftCount = emails.filter((e) => e.status === 'draft').length
  const sentCount = emails.filter((e) => e.status === 'sent').length

  return (
    <div className="p-8">
      <div className="mb-6">
        <Link href={`/campaigns/${id}`} className="text-sm text-gray-400 hover:text-gray-600 flex items-center gap-1 mb-4">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Retour à la campagne
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Mails générés</h1>
            <p className="text-sm text-gray-500 mt-1">
              {draftCount} brouillon{draftCount !== 1 ? 's' : ''} · {sentCount} envoyé{sentCount !== 1 ? 's' : ''}
            </p>
          </div>
          {draftCount > 0 && (
            <button
              onClick={sendAll}
              disabled={!!sending}
              className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              Tout envoyer ({draftCount})
            </button>
          )}
        </div>

        {message && (
          <p className="mt-3 text-sm text-brand-600 bg-brand-50 border border-brand-100 rounded-lg px-3 py-2">
            {message}
          </p>
        )}
      </div>

      {emails.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-sm">Aucun mail généré. Lance la génération depuis la campagne.</p>
          <Link href={`/campaigns/${id}`} className="text-brand-500 text-sm mt-2 inline-block hover:underline">
            Retour à la campagne →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {emails.map((email) => (
            <div
              key={email.id}
              className="bg-white border border-gray-100 rounded-xl overflow-hidden"
            >
              {/* Header */}
              <div
                className="px-5 py-4 flex items-center justify-between gap-4 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => setExpanded(expanded === email.id ? null : email.id)}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-gray-900 truncate">{email.company.name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                      email.status === 'sent'
                        ? 'bg-green-50 text-green-600'
                        : 'bg-yellow-50 text-yellow-600'
                    }`}>
                      {email.status === 'sent' ? 'Envoyé' : 'Brouillon'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 truncate mt-0.5">{email.subject}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {email.status === 'draft' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); sendEmail(email.id) }}
                      disabled={sending === email.id}
                      className="text-xs bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition-colors"
                    >
                      {sending === email.id ? 'Envoi...' : 'Envoyer'}
                    </button>
                  )}
                  <svg
                    className={`w-4 h-4 text-gray-400 transition-transform ${expanded === email.id ? 'rotate-180' : ''}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Body */}
              {expanded === email.id && (
                <div className="px-5 pb-5 border-t border-gray-50">
                  <p className="text-xs text-gray-400 mt-3 mb-1">Objet</p>
                  <p className="text-sm text-gray-800 mb-3">{email.subject}</p>
                  <p className="text-xs text-gray-400 mb-1">Corps</p>
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 rounded-lg p-4">
                    {email.body}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
