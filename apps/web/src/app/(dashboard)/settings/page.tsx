'use client'

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'

interface EmailStatus {
  connected: boolean
  provider?: 'gmail'
  oauthEmail?: string
}

const PROVIDER_LABELS: Record<string, string> = {
  gmail: 'Gmail',
}

export default function SettingsPage() {
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<EmailStatus>({ connected: false })
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [disconnecting, setDisconnecting] = useState(false)

  const fetchStatus = useCallback(async () => {
    const res = await fetch('/api/settings/email')
    if (res.ok) setStatus(await res.json())
  }, [])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')
    if (connected) {
      setToast({ message: `${PROVIDER_LABELS[connected] ?? connected} connecté avec succès !`, type: 'success' })
      fetchStatus()
    } else if (error) {
      setToast({ message: `Erreur : ${error}`, type: 'error' })
    }
  }, [searchParams, fetchStatus])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(t)
  }, [toast])

  async function handleDisconnect() {
    setDisconnecting(true)
    const res = await fetch('/api/auth/connect/disconnect', { method: 'DELETE' })
    if (res.ok) {
      setStatus({ connected: false })
      setToast({ message: 'Compte email déconnecté.', type: 'success' })
    } else {
      setToast({ message: 'Erreur lors de la déconnexion.', type: 'error' })
    }
    setDisconnecting(false)
  }

  return (
    <div className="p-8 max-w-xl">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-slate-900">Paramètres</h1>
        <p className="text-sm text-slate-400 mt-0.5">Connectez votre boîte mail pour envoyer vos candidatures</p>
      </div>

      {toast && (
        <div
          className={`mb-6 text-sm rounded-lg px-4 py-3 ${
            toast.type === 'success'
              ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
              : 'text-red-700 bg-red-50 border border-red-200'
          }`}
        >
          {toast.message}
        </div>
      )}

      <div className="bg-white border border-slate-100 rounded-xl p-6 space-y-5">
        <div className="pb-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">Compte email d&apos;envoi</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Vos candidatures seront envoyées directement depuis votre boîte mail.
          </p>
        </div>

        {status.connected ? (
          <div className="flex items-center justify-between gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">
                  {PROVIDER_LABELS[status.provider ?? ''] ?? status.provider} connecté
                </p>
                {status.oauthEmail && (
                  <p className="text-xs text-slate-500 mt-0.5">{status.oauthEmail}</p>
                )}
              </div>
            </div>
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="text-xs text-slate-500 hover:text-red-600 border border-slate-200 hover:border-red-200 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50"
            >
              {disconnecting ? 'Déconnexion...' : 'Déconnecter'}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <a
              href="/api/auth/connect/gmail"
              className="flex items-center gap-3 w-full border border-slate-200 hover:border-slate-300 hover:bg-slate-50 rounded-lg px-4 py-3 transition-colors group"
            >
              <GmailIcon />
              <span className="text-sm font-medium text-slate-700">Connecter Gmail</span>
              <svg className="w-4 h-4 text-slate-400 group-hover:text-slate-600 ml-auto transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </a>

<p className="text-xs text-slate-400 pt-1">
              Nous demandons uniquement la permission d&apos;envoyer des emails en votre nom. Vos messages ne sont jamais stockés.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function GmailIcon() {
  return (
    <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
      <path fill="#EA4335" d="M7 40h34V20L24 32 7 20z" />
      <path fill="#FBBC05" d="M41 8H7L24 20z" />
      <path fill="#34A853" d="M41 8l6 6v26l-6-6z" />
      <path fill="#4285F4" d="M7 8L1 14v26l6-6z" />
      <path fill="#C5221F" d="M7 8v12l17 12 17-12V8L24 20z" />
    </svg>
  )
}

