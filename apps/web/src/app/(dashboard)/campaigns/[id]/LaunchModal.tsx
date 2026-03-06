'use client'

import { useEffect, useRef, useState } from 'react'

interface LaunchModalProps {
  campaignId: string
  totalDraft: number
  onClose: () => void
  onSuccess: () => void
}

interface EmailStatus {
  connected: boolean
  provider?: string
  oauthEmail?: string
}

const HOURS = Array.from({ length: 24 }, (_, i) => i)

export default function LaunchModal({ campaignId, totalDraft, onClose, onSuccess }: LaunchModalProps) {
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null)
  const [dailyLimit, setDailyLimit] = useState(Math.min(50, totalDraft))
  const [sendStartHour, setSendStartHour] = useState(8)
  const [sendEndHour, setSendEndHour] = useState(18)
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState('')
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/settings/email').then(r => r.json()).then(setEmailStatus)
  }, [])

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose()
  }

  const days = Math.ceil(totalDraft / dailyLimit)
  const intervalMinutes = Math.floor(1440 / dailyLimit)
  const windowHours = sendEndHour - sendStartHour
  const isWindowValid = windowHours > 0

  async function handleLaunch() {
    if (!isWindowValid) {
      setError('L\'heure de fin doit être après l\'heure de début')
      return
    }
    setLaunching(true)
    setError('')
    const res = await fetch(`/api/campaigns/${campaignId}/launch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dailyLimit, sendStartHour, sendEndHour }),
    })
    const data = await res.json()
    if (!res.ok) {
      setError(data.error ?? 'Erreur lors du lancement')
      setLaunching(false)
      return
    }
    onSuccess()
  }

  const providerLabel = emailStatus?.provider === 'gmail'
    ? 'Gmail'
    : emailStatus?.provider === 'microsoft'
      ? 'Outlook'
      : ''

  function fmtHour(h: number) {
    return `${String(h).padStart(2, '0')}h00`
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">

        {/* En-tête */}
        <div className="px-6 pt-6 pb-4 border-b border-slate-100 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Activer la campagne</h2>
            <p className="text-sm text-slate-400 mt-0.5">
              {totalDraft} mail{totalDraft !== 1 ? 's' : ''} prêt{totalDraft !== 1 ? 's' : ''} à envoyer automatiquement
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full hover:bg-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors shrink-0"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">

          {/* ── Slider volume journalier ─────────────────────────────────── */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Mails par jour</p>
              <span className="text-sm font-bold text-slate-900">{dailyLimit}</span>
            </div>
            <input
              type="range"
              min={1}
              max={500}
              value={dailyLimit}
              onChange={e => setDailyLimit(Number(e.target.value))}
              className="w-full accent-slate-900 cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>1</span>
              <span>500</span>
            </div>
          </div>

          {/* ── Fenêtre horaire ──────────────────────────────────────────── */}
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Fenêtre d&apos;envoi</p>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="text-xs text-slate-400 mb-1 block">De</label>
                <select
                  value={sendStartHour}
                  onChange={e => setSendStartHour(Number(e.target.value))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900 transition"
                >
                  {HOURS.slice(0, 23).map(h => (
                    <option key={h} value={h}>{fmtHour(h)}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="text-xs text-slate-400 mb-1 block">À</label>
                <select
                  value={sendEndHour}
                  onChange={e => setSendEndHour(Number(e.target.value))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900 transition"
                >
                  {HOURS.slice(1).map(h => (
                    <option key={h} value={h}>{fmtHour(h)}</option>
                  ))}
                </select>
              </div>
            </div>
            {!isWindowValid && (
              <p className="text-xs text-red-500 mt-1.5">L&apos;heure de fin doit être après l&apos;heure de début</p>
            )}
          </div>

          {/* ── Compte email d'envoi ─────────────────────────────────────── */}
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Compte d&apos;envoi</p>
            {emailStatus === null ? (
              <div className="h-12 bg-slate-50 rounded-xl animate-pulse" />
            ) : emailStatus.connected ? (
              <div className="flex items-center gap-3 bg-slate-50 rounded-xl px-4 py-3">
                <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                  <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-800">{emailStatus.oauthEmail}</p>
                  <p className="text-xs text-slate-400">{providerLabel}</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                <div className="flex items-center gap-2.5">
                  <svg className="w-4 h-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-sm text-amber-800">Aucune boîte mail connectée</p>
                </div>
                <a href="/settings" className="text-xs font-medium text-amber-700 hover:text-amber-900 underline shrink-0">
                  Connecter →
                </a>
              </div>
            )}
          </div>

          {/* ── Résumé ───────────────────────────────────────────────────── */}
          <div className="bg-slate-50 rounded-xl px-4 py-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Fenêtre d&apos;envoi</span>
              <span className="font-semibold text-slate-900">{fmtHour(sendStartHour)} – {fmtHour(sendEndHour)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Intervalle entre envois</span>
              <span className="font-semibold text-slate-900">
                {intervalMinutes >= 60
                  ? `~${Math.round(intervalMinutes / 60)}h`
                  : `~${intervalMinutes} min`}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Durée estimée</span>
              <span className="font-semibold text-slate-900">
                {days <= 1 ? 'Tout envoyé aujourd\'hui' : `${days} jour${days !== 1 ? 's' : ''}`}
              </span>
            </div>
            <p className="text-xs text-slate-400 pt-1 border-t border-slate-100">
              Premier envoi dans les prochaines minutes après activation.
            </p>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3.5 py-2.5">
              {error}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 pb-6 flex items-center gap-3">
          <button
            onClick={onClose}
            disabled={launching}
            className="flex-1 border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-50 font-medium text-sm rounded-xl py-2.5 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={handleLaunch}
            disabled={launching || !emailStatus?.connected || totalDraft === 0 || !isWindowValid}
            className="flex-1 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 text-white font-semibold text-sm rounded-xl py-2.5 transition-colors flex items-center justify-center gap-2"
          >
            {launching ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Activation...
              </>
            ) : (
              'Activer la campagne'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
