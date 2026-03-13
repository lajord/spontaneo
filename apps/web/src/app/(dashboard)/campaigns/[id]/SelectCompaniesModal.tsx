'use client'

import { useState, useEffect } from 'react'

const CREDITS_PER_COMPANY = 2
const APOLLO_EXTRA_CREDITS = 50

type EnrichMode = 'basic' | 'ranked'

type Props = {
    open: boolean
    totalCompanies: number
    onConfirm: (count: number, enrichMode: EnrichMode) => void
    onCancel: () => void
}

export default function SelectCompaniesModal({ open, totalCompanies, onConfirm, onCancel }: Props) {
    const min = Math.min(10, totalCompanies)
    const max = totalCompanies
    const [count, setCount] = useState(Math.min(30, max))
    const [enrichMode, setEnrichMode] = useState<EnrichMode>('basic')

    // Recale le count à chaque ouverture du modal pour refléter le nombre actuel d'entreprises
    useEffect(() => {
        if (open) {
            setCount(prev => Math.min(prev, totalCompanies))
        }
    }, [open, totalCompanies])

    if (!open) return null

    const baseCredits = count * CREDITS_PER_COMPANY
    const totalCredits = enrichMode === 'ranked' ? baseCredits + APOLLO_EXTRA_CREDITS : baseCredits
    const pct = max <= min ? 100 : ((count - min) / (max - min)) * 100

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Overlay */}
            <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onCancel} />

            {/* Panel */}
            <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 overflow-hidden flex flex-col border border-slate-100">

                {/* Header */}
                <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/50">
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Combien d&apos;entreprises contacter ?</h2>
                        <p className="text-sm text-slate-500 mt-1">
                            {totalCompanies} entreprise{totalCompanies > 1 ? 's' : ''} trouvée{totalCompanies > 1 ? 's' : ''} · ajustez selon vos besoins
                        </p>
                    </div>
                    <button
                        onClick={onCancel}
                        className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="px-8 py-8 space-y-8">

                    {/* Valeur choisie */}
                    <div className="text-center">
                        <span className="text-6xl font-bold text-slate-900 tabular-nums">{count}</span>
                        <span className="text-xl text-slate-400 ml-2 font-medium">entreprise{count > 1 ? 's' : ''}</span>
                    </div>

                    {/* Slider */}
                    <div className="space-y-3">
                        <input
                            type="range"
                            min={min}
                            max={max}
                            step={1}
                            value={count}
                            onChange={e => setCount(Number(e.target.value))}
                            className="w-full accent-brand-500 h-2 cursor-pointer"
                            style={{
                                background: `linear-gradient(to right, var(--color-brand-500, #6366f1) ${pct}%, #e2e8f0 ${pct}%)`
                            }}
                        />
                        <div className="flex justify-between text-xs text-slate-400 font-medium">
                            <span>{min} min</span>
                            <span>{max} max</span>
                        </div>
                    </div>

                    {/* Mode d'enrichissement */}
                    <div className="space-y-3">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Mode d&apos;enrichissement</p>
                        <div className="grid grid-cols-2 gap-3">
                            <button
                                type="button"
                                onClick={() => setEnrichMode('basic')}
                                className={`text-left p-4 rounded-xl border-2 transition-colors ${enrichMode === 'basic' ? 'border-brand-500 bg-brand-50' : 'border-slate-200 bg-white hover:border-slate-300'}`}
                            >
                                <div className="flex items-center gap-2 mb-1.5">
                                    <div className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 ${enrichMode === 'basic' ? 'border-brand-500 bg-brand-500' : 'border-slate-300'}`}>
                                        {enrichMode === 'basic' && <div className="w-1 h-1 rounded-full bg-white" />}
                                    </div>
                                    <p className={`text-sm font-semibold ${enrichMode === 'basic' ? 'text-brand-700' : 'text-slate-800'}`}>Standard</p>
                                </div>
                                <p className="text-xs text-slate-500 leading-relaxed pl-5">Enrichissement standard (plus rapide)</p>
                            </button>
                            <button
                                type="button"
                                onClick={() => setEnrichMode('ranked')}
                                className={`text-left p-4 rounded-xl border-2 transition-colors ${enrichMode === 'ranked' ? 'border-brand-500 bg-brand-50' : 'border-slate-200 bg-white hover:border-slate-300'}`}
                            >
                                <div className="flex items-center gap-2 mb-1.5">
                                    <div className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 ${enrichMode === 'ranked' ? 'border-brand-500 bg-brand-500' : 'border-slate-300'}`}>
                                        {enrichMode === 'ranked' && <div className="w-1 h-1 rounded-full bg-white" />}
                                    </div>
                                    <p className={`text-sm font-semibold ${enrichMode === 'ranked' ? 'text-brand-700' : 'text-slate-800'}`}>
                                        Avancé
                                        <span className="ml-1.5 text-xs font-normal px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">+{APOLLO_EXTRA_CREDITS} crédits</span>
                                    </p>
                                </div>
                                <p className="text-xs text-slate-500 leading-relaxed pl-5">Enrichissement avancé pour récupérer plus de mails de décideurs</p>
                            </button>
                        </div>
                    </div>

                    {/* Coût en crédits */}
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-6 py-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg bg-brand-100 flex items-center justify-center shrink-0">
                                <svg className="w-5 h-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-slate-800">Crédits nécessaires</p>
                                <p className="text-xs text-slate-500">
                                    {count} × {CREDITS_PER_COMPANY} crédits
                                    {enrichMode === 'ranked' && (
                                        <span className="text-amber-600"> + {APOLLO_EXTRA_CREDITS} crédits Apollo</span>
                                    )}
                                </p>
                            </div>
                        </div>
                        <div className="text-right">
                            <span className="text-2xl font-bold text-slate-900 tabular-nums">{totalCredits}</span>
                            <span className="text-sm text-slate-500 ml-1">crédits</span>
                        </div>
                    </div>

                    {/* Info rapide */}
                    <p className="text-xs text-slate-400 text-center leading-relaxed">
                        Vous pourrez toujours relancer la génération avec plus d&apos;entreprises plus tard.
                    </p>
                </div>

                {/* Footer */}
                <div className="px-8 py-5 border-t border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/50">
                    <button
                        onClick={onCancel}
                        className="text-sm text-slate-600 hover:text-slate-900 font-medium px-5 py-2.5 rounded-lg hover:bg-slate-200/60 border border-transparent transition-colors"
                    >
                        Annuler
                    </button>
                    <button
                        onClick={() => onConfirm(count, enrichMode)}
                        className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 shadow border border-brand-500 text-white text-sm font-semibold px-6 py-2.5 rounded-lg transition-transform hover:-translate-y-px active:translate-y-0"
                    >
                        Suivant
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    )
}
