'use client'

import { useEffect, useRef, useState } from 'react'

interface LaunchModalProps {
  campaignId: string
  totalDraft: number
  onClose: () => void
  onSuccess: (pending?: boolean) => void
  isGenerating?: boolean
}

interface EmailStatus {
  connected: boolean
  provider?: string
  oauthEmail?: string
}

const HOURS = Array.from({ length: 24 }, (_, i) => i)

function fmtHour(h: number) {
  return `${String(h).padStart(2, '0')}h00`
}

export default function LaunchModal({ campaignId, totalDraft, onClose, onSuccess, isGenerating }: LaunchModalProps) {
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null)
  const defaultDailyLimit = isGenerating ? 120 : Math.min(50, Math.max(1, totalDraft))
  const [dailyLimit, setDailyLimit] = useState(defaultDailyLimit)
  const [inputValue, setInputValue] = useState(String(defaultDailyLimit))
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

  function handleDailyLimitChange(val: number) {
    const clamped = Math.min(500, Math.max(1, val))
    setDailyLimit(clamped)
    setInputValue(String(clamped))
  }

  function handleInputBlur() {
    const parsed = parseInt(inputValue, 10)
    if (isNaN(parsed)) setInputValue(String(dailyLimit))
    else handleDailyLimitChange(parsed)
  }

  const days = Math.ceil(totalDraft / dailyLimit)
  const windowHours = sendEndHour - sendStartHour
  const isWindowValid = windowHours > 0
  const intervalMinutes = Math.floor((windowHours * 60) / dailyLimit)

  const providerLabel = emailStatus?.provider === 'gmail'
    ? 'Gmail'
    : emailStatus?.provider === 'microsoft'
      ? 'Outlook'
      : ''

  async function handleLaunch() {
    if (!isWindowValid) {
      setError("L'heure de fin doit être après l'heure de début")
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
    onSuccess(data.pendingGeneration)
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="px-8 pt-7 pb-5 border-b border-slate-100 flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Activer la campagne</h2>
              <p className="text-sm text-slate-400 mt-0.5">
                {isGenerating
                  ? "La campagne démarrera automatiquement à la fin de la génération"
                  : `${totalDraft} email${totalDraft !== 1 ? 's' : ''} prêt${totalDraft !== 1 ? 's' : ''} à envoyer`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors shrink-0"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* ── Corps ──────────────────────────────────────────────────────── */}
        <div className="px-8 py-7 space-y-8">

          {/* Volume journalier */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">Emails par jour</p>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onBlur={handleInputBlur}
                  onKeyDown={e => { if (e.key === 'Enter') handleInputBlur() }}
                  className="w-20 border border-slate-200 rounded-lg px-3 py-1.5 text-sm font-bold text-slate-900 text-center focus:outline-none focus:ring-2 focus:ring-slate-900 transition"
                />
                <span className="text-sm text-slate-400">/ jour</span>
              </div>
            </div>

            {/* Slider stylisé */}
            <div className="relative py-2">
              <div className="relative h-2 bg-slate-100 rounded-full">
                <div
                  className="absolute left-0 top-0 h-2 bg-slate-900 rounded-full transition-all"
                  style={{ width: `${((dailyLimit - 1) / 499) * 100}%` }}
                />
              </div>
              <input
                type="range"
                min={1}
                max={500}
                value={dailyLimit}
                onChange={e => handleDailyLimitChange(Number(e.target.value))}
                className="absolute inset-0 w-full opacity-0 cursor-pointer h-full"
              />
              {/* Thumb visible */}
              <div
                className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white border-2 border-slate-900 rounded-full shadow-md pointer-events-none transition-all"
                style={{ left: `calc(${((dailyLimit - 1) / 499) * 100}% - 10px)` }}
              />
            </div>

            <div className="flex justify-between text-[11px] text-slate-400 mt-2">
              <span>1</span>
              <span className="text-slate-500 font-medium">Conseil : ~{Math.max(1, windowHours * 12)} / jour</span>
              <span>500</span>
            </div>
          </div>

          {/* Fenêtre horaire */}
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-4">Fenêtre d&apos;envoi</p>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <label className="text-xs text-slate-400 mb-1.5 block">De</label>
                <select
                  value={sendStartHour}
                  onChange={e => setSendStartHour(Number(e.target.value))}
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900 transition bg-white"
                >
                  {HOURS.slice(0, 23).map(h => (
                    <option key={h} value={h}>{fmtHour(h)}</option>
                  ))}
                </select>
              </div>
              <div className="mt-5 text-slate-300 font-light text-lg">→</div>
              <div className="flex-1">
                <label className="text-xs text-slate-400 mb-1.5 block">À</label>
                <select
                  value={sendEndHour}
                  onChange={e => setSendEndHour(Number(e.target.value))}
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900 transition bg-white"
                >
                  {HOURS.slice(1).map(h => (
                    <option key={h} value={h}>{fmtHour(h)}</option>
                  ))}
                </select>
              </div>
            </div>
            {!isWindowValid && (
              <p className="text-xs text-red-500 mt-2">L&apos;heure de fin doit être après l&apos;heure de début</p>
            )}
            <p className="text-xs text-slate-400 mt-2">Aucun envoi le samedi et dimanche.</p>
          </div>

          {/* Compte d'envoi */}
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-4">Compte d&apos;envoi</p>
            {emailStatus === null ? (
              <div className="h-14 bg-slate-50 rounded-xl animate-pulse" />
            ) : emailStatus.connected ? (
              <div className="flex items-center gap-4 border border-slate-200 rounded-xl px-5 py-4">
                <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                  <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800">{emailStatus.oauthEmail}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{providerLabel}</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-4 bg-amber-50 border border-amber-200 rounded-xl px-5 py-4">
                <p className="text-sm text-amber-800">Aucune boîte mail connectée</p>
                <a href="/settings" className="text-xs font-semibold text-amber-700 hover:text-amber-900 shrink-0">
                  Connecter →
                </a>
              </div>
            )}
          </div>

          {/* Résumé */}
          <div className="border border-slate-100 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
              <span className="text-sm text-slate-500">Fenêtre d&apos;envoi</span>
              <span className="text-sm font-semibold text-slate-900">{fmtHour(sendStartHour)} – {fmtHour(sendEndHour)}</span>
            </div>
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
              <span className="text-sm text-slate-500">Intervalle entre envois</span>
              <span className="text-sm font-semibold text-slate-900">
                {intervalMinutes <= 0 ? '< 1 min' : intervalMinutes >= 60
                  ? `~${Math.round(intervalMinutes / 60)}h`
                  : `~${intervalMinutes} min`}
              </span>
            </div>
            <div className="flex items-center justify-between px-5 py-3.5">
              <span className="text-sm text-slate-500">Durée estimée</span>
              <span className="text-sm font-semibold text-slate-900">
                {isGenerating ? 'Variable' : days <= 1 ? "Aujourd'hui" : `${days} jour${days !== 1 ? 's' : ''}`}
              </span>
            </div>
          </div>

        </div>

        {/* ── Erreur ─────────────────────────────────────────────────────── */}
        {error && (
          <div className="mx-8 mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
            {error}
          </div>
        )}

        {/* ── Actions ────────────────────────────────────────────────────── */}
        <div className="px-8 pb-7 flex items-center gap-3">
          <button
            onClick={onClose}
            disabled={launching}
            className="px-6 border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-50 font-medium text-sm rounded-xl py-3 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={handleLaunch}
            disabled={launching || !emailStatus?.connected || (!isGenerating && totalDraft === 0) || !isWindowValid}
            className="flex-1 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 text-white font-semibold text-sm rounded-xl py-3 transition-colors flex items-center justify-center gap-2"
          >
            {launching ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Activation...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Activer la campagne
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  )
}
