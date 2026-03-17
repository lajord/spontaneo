'use client'

import { useState } from 'react'

const CREDITS_PER_COMPANY = 2

interface PaywallModalProps {
  open: boolean
  totalCompanies: number
  onConfirm: (selectedCount: number) => void
  onCancel: () => void
}

export default function PaywallModal({ open, totalCompanies, onConfirm, onCancel }: PaywallModalProps) {
  const [count, setCount] = useState(totalCompanies)
  const [inputValue, setInputValue] = useState(String(totalCompanies))

  if (!open) return null

  const credits = count * CREDITS_PER_COMPANY

  function handleCountChange(val: number) {
    const clamped = Math.min(totalCompanies, Math.max(1, val))
    setCount(clamped)
    setInputValue(String(clamped))
  }

  function handleInputBlur() {
    const parsed = parseInt(inputValue, 10)
    if (isNaN(parsed)) setInputValue(String(count))
    else handleCountChange(parsed)
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4">
          <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center mb-4">
            <svg className="w-6 h-6 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-1">Passer à l&apos;étape suivante</h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            Choisissez combien d&apos;entreprises vous souhaitez contacter.
            Chaque entreprise coûte <span className="font-semibold text-slate-700">{CREDITS_PER_COMPANY} crédits</span>.
          </p>
        </div>

        {/* Slider */}
        <div className="mx-6 mb-4 p-5 bg-slate-50 border border-slate-100 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-600 font-medium">Nombre d&apos;entreprises</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={totalCompanies}
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onBlur={handleInputBlur}
                onKeyDown={e => { if (e.key === 'Enter') handleInputBlur() }}
                className="w-16 border border-slate-200 rounded-lg px-2 py-1 text-sm font-bold text-slate-900 text-center focus:outline-none focus:ring-2 focus:ring-slate-900 transition"
              />
              <span className="text-sm text-slate-400">/ {totalCompanies}</span>
            </div>
          </div>

          <div className="relative py-2">
            <div className="relative h-2 bg-slate-200 rounded-full">
              <div
                className="absolute left-0 top-0 h-2 bg-slate-900 rounded-full transition-all"
                style={{ width: totalCompanies <= 1 ? '100%' : `${((count - 1) / (totalCompanies - 1)) * 100}%` }}
              />
            </div>
            <input
              type="range"
              min={1}
              max={totalCompanies}
              value={count}
              onChange={e => handleCountChange(Number(e.target.value))}
              className="absolute inset-0 w-full opacity-0 cursor-pointer h-full"
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white border-2 border-slate-900 rounded-full shadow-md pointer-events-none transition-all"
              style={{ left: totalCompanies <= 1 ? 'calc(100% - 10px)' : `calc(${((count - 1) / (totalCompanies - 1)) * 100}% - 10px)` }}
            />
          </div>

          <div className="flex items-center justify-between mt-1">
            <span className="text-[10px] text-slate-400">1</span>
            <span className="text-[10px] text-slate-400">{totalCompanies}</span>
          </div>
        </div>

        {/* Credits summary */}
        <div className="mx-6 mb-6 p-4 bg-slate-900 rounded-xl flex items-center justify-between">
          <span className="text-sm text-slate-300 font-medium">Crédits nécessaires</span>
          <span className="text-lg font-bold text-white tabular-nums">{credits}</span>
        </div>

        {/* Actions */}
        <div className="px-6 pb-6 flex items-center gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={() => onConfirm(count)}
            className="flex-1 px-4 py-2.5 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
          >
            Continuer ({credits} crédits)
          </button>
        </div>
      </div>
    </div>
  )
}
