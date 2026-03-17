'use client'

import { useState, useEffect, useRef } from 'react'

type EmailRecipient = {
    id: string
    subject: string
    body: string
    to: string | null
    recipientName: string | null
    generatedLm: string | null
    status: string
    sentAt?: string | null
}

type EnrichedContact = {
    type: 'generique' | 'specialise'
    nom?: string | null
    prenom?: string | null
    role?: string | null
    mail?: string | null
    genre?: string | null
}

type EnrichedData = {
    resultats: EnrichedContact[]
}

type GeneratedBlock = {
    companyId: string
    companyName: string
    companyAddress: string | null
    enriched: EnrichedData
    emails: EmailRecipient[]
}

interface Props {
    block: GeneratedBlock | null
    campaignName: string
    onClose: () => void
    sending: string | null
    onSend: (emailId: string) => void
}

function LmDocxViewer({ emailId, fallback }: { emailId: string; fallback: string }) {
    const containerRef = useRef<HTMLDivElement>(null)
    const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

    useEffect(() => {
        let cancelled = false
        async function render() {
            try {
                const { renderAsync } = await import('docx-preview')
                const res = await fetch(`/api/emails/${emailId}/lm`)
                if (!res.ok) throw new Error('no file')
                const blob = await res.blob()
                if (cancelled || !containerRef.current) return
                await renderAsync(blob, containerRef.current, undefined, {
                    inWrapper: false, ignoreWidth: false, ignoreHeight: false,
                    ignoreFonts: false, breakPages: false, useBase64URL: true,
                })
                if (!cancelled) setStatus('ok')
            } catch {
                if (!cancelled) setStatus('error')
            }
        }
        render()
        return () => { cancelled = true }
    }, [emailId])

    if (status === 'error') {
        return (
            <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed bg-slate-50 rounded-lg px-3.5 py-3">
                {fallback}
            </pre>
        )
    }

    return (
        <div className="relative">
            {status === 'loading' && (
                <div className="px-4 py-6 text-sm text-slate-500 text-center bg-slate-50 rounded-lg">
                    Chargement de la lettre…
                </div>
            )}
            <div
                ref={containerRef}
                className={`docx-preview-container bg-white rounded-lg border border-slate-200 overflow-auto ${status === 'loading' ? 'hidden' : ''}`}
                style={{ maxHeight: '400px' }}
            />
            {status === 'ok' && (
                <a
                    href={`/api/emails/${emailId}/lm`}
                    download="lettre-motivation.docx"
                    className="mt-2 inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
                >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Télécharger le DOCX
                </a>
            )}
        </div>
    )
}

export default function CompanyDetailView({ block, onClose }: Props) {
    const [expandedEmail, setExpandedEmail] = useState<string | null>(null)
    const [expandedLm, setExpandedLm] = useState<Set<string>>(new Set())
    const [decideurOpen, setDecideurOpen] = useState(false)
    const isOpen = block !== null

    // Reset state when company changes
    useEffect(() => {
        setExpandedEmail(null)
        setExpandedLm(new Set())
        setDecideurOpen(false)
    }, [block?.companyId])

    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [onClose])

    function toggleLm(emailId: string) {
        setExpandedLm(prev => {
            const next = new Set(prev)
            next.has(emailId) ? next.delete(emailId) : next.add(emailId)
            return next
        })
    }

    const contacts = block?.enriched?.resultats ?? []
    const specialises = contacts.filter(c => c.type === 'specialise')
    const draftEmails = block?.emails.filter(e => e.status === 'draft') ?? []
    const initials = block?.companyName.slice(0, 2).toUpperCase() ?? ''

    return (
        <>
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-black/25 z-40 transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
                onClick={onClose}
            />

            {/* Sidebar */}
            <div className={`fixed right-0 top-0 h-full w-[780px] max-w-[95vw] bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
                {block && (
                    <>
                        {/* ── Header ─────────────────────────────────────────── */}
                        <div className="px-6 pt-5 pb-4 border-b border-slate-100 shrink-0">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-10 h-10 rounded-xl bg-slate-900 text-white flex items-center justify-center text-sm font-bold shrink-0">
                                        {initials}
                                    </div>
                                    <div className="min-w-0">
                                        <h2 className="text-base font-bold text-slate-900 leading-tight truncate">{block.companyName}</h2>
                                        {block.companyAddress && (
                                            <p className="text-xs text-slate-500 mt-0.5 truncate">{block.companyAddress}</p>
                                        )}
                                    </div>
                                </div>
                                <button
                                    onClick={onClose}
                                    className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-600 shrink-0"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>

                            {/* Stats rapides */}
                            <div className="flex gap-3 mt-4">
                                <div className="flex items-center gap-1.5 text-xs text-slate-600">
                                    <svg className="w-3.5 h-3.5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                                    </svg>
                                    <span className="font-medium">{specialises.length}</span> décideur{specialises.length > 1 ? 's' : ''}
                                </div>
                                <span className="text-slate-200">·</span>
                                <div className="flex items-center gap-1.5 text-xs text-slate-600">
                                    <svg className="w-3.5 h-3.5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                    </svg>
                                    <span className="font-medium">{draftEmails.length}</span> email{draftEmails.length > 1 ? 's' : ''} généré{draftEmails.length > 1 ? 's' : ''}
                                </div>
                            </div>
                        </div>

                        {/* ── Corps scrollable ─────────────────────────────── */}
                        <div className="flex-1 overflow-y-auto">

                            {/* ── Emails récupérés ─────────────────────────── */}
                            <div className="px-6 py-5 border-b border-slate-100">
                                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-3">
                                    Emails récupérés
                                    {contacts.filter(c => c.mail).length > 0 && (
                                        <span className="ml-2 normal-case font-normal">({contacts.filter(c => c.mail).length})</span>
                                    )}
                                </p>

                                {contacts.filter(c => c.mail).length === 0 ? (
                                    <p className="text-sm text-slate-400 italic">Aucun email trouvé</p>
                                ) : (
                                    <div className="flex flex-wrap gap-2">
                                        {contacts.filter(c => c.mail).map((c, i) => (
                                            <div key={i} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono ${
                                                c.type === 'specialise'
                                                    ? 'bg-brand-50 border-brand-100 text-brand-700'
                                                    : 'bg-slate-50 border-slate-200 text-slate-600'
                                            }`}>
                                                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.type === 'specialise' ? 'bg-brand-400' : 'bg-slate-400'}`} />
                                                {c.mail}
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Sous-partie : Décideurs identifiés */}
                                {specialises.filter(c => c.nom || c.prenom).length > 0 && (
                                    <div className="mt-4 pt-3 border-t border-slate-100">
                                        <button
                                            onClick={() => setDecideurOpen(v => !v)}
                                            className="flex items-center gap-2 w-full text-left group"
                                        >
                                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest flex-1">
                                                Décideurs identifiés
                                                <span className="ml-1.5 normal-case font-normal">({specialises.filter(c => c.nom || c.prenom).length})</span>
                                            </p>
                                            <svg
                                                className={`w-3 h-3 text-slate-400 transition-transform shrink-0 ${decideurOpen ? 'rotate-180' : ''}`}
                                                fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                            >
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                                            </svg>
                                        </button>
                                        {decideurOpen && (
                                            <div className="divide-y divide-slate-100 mt-2">
                                                {specialises.filter(c => c.nom || c.prenom).map((c, i) => {
                                                    const name = [c.prenom, c.nom].filter(Boolean).join(' ')
                                                    return (
                                                        <div key={i} className="flex items-center gap-2.5 py-1.5">
                                                            <div className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[9px] font-bold shrink-0">
                                                                {[c.prenom?.[0], c.nom?.[0]].filter(Boolean).join('').toUpperCase() || '?'}
                                                            </div>
                                                            <span className="text-xs font-semibold text-slate-700 shrink-0">{name}</span>
                                                            {c.role && <span className="text-[11px] text-slate-400 truncate">· {c.role}</span>}
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Emails */}
                            <div className="px-6 py-5">
                                <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-3">
                                    Emails générés
                                    {draftEmails.length > 0 && <span className="ml-1.5 normal-case font-normal text-slate-400">({draftEmails.length})</span>}
                                </p>

                                {draftEmails.length === 0 ? (
                                    <p className="text-sm text-slate-400 italic">Aucun email généré</p>
                                ) : (
                                    <div className="space-y-3">
                                        {draftEmails.map((email, idx) => {
                                            const isOpen = expandedEmail === email.id
                                            const lmOpen = expandedLm.has(email.id)
                                            return (
                                                <div key={email.id} className="border border-slate-200 rounded-xl overflow-hidden bg-white">
                                                    {/* Email header */}
                                                    <div
                                                        className="px-4 py-3.5 flex items-center justify-between gap-3 cursor-pointer hover:bg-slate-50 transition-colors"
                                                        onClick={() => setExpandedEmail(isOpen ? null : email.id)}
                                                    >
                                                        <div className="min-w-0 flex-1">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-[11px] font-bold text-slate-400">#{idx + 1}</span>
                                                                <span className="text-sm font-semibold text-slate-800 truncate">
                                                                    {email.recipientName && email.recipientName !== email.to
                                                                        ? email.recipientName
                                                                        : 'Contact général'}
                                                                </span>
                                                            </div>
                                                            {email.to && (
                                                                <p className="text-xs font-mono text-slate-400 truncate mt-0.5 pl-5">{email.to}</p>
                                                            )}
                                                            {!isOpen && (
                                                                <p className="text-xs text-slate-500 truncate mt-1 pl-5">{email.subject}</p>
                                                            )}
                                                        </div>
                                                        <svg
                                                            className={`w-3.5 h-3.5 text-slate-400 transition-transform shrink-0 ${isOpen ? 'rotate-180' : ''}`}
                                                            fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                                        >
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                        </svg>
                                                    </div>

                                                    {/* Corps déplié */}
                                                    {isOpen && (
                                                        <div className="border-t border-slate-100 px-4 pb-4 pt-3 space-y-3 bg-slate-50/50">
                                                            <div>
                                                                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-1">Objet</p>
                                                                <p className="text-sm text-slate-800 bg-white border border-slate-200 rounded-lg px-3 py-2">{email.subject}</p>
                                                            </div>
                                                            <div>
                                                                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-1">Corps</p>
                                                                <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed bg-white border border-slate-200 rounded-lg px-3 py-3 max-h-64 overflow-y-auto">
                                                                    {email.body}
                                                                </pre>
                                                            </div>

                                                            {email.generatedLm && (
                                                                <div>
                                                                    <button
                                                                        onClick={() => toggleLm(email.id)}
                                                                        className="flex items-center gap-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest hover:text-slate-600 transition-colors w-full py-1"
                                                                    >
                                                                        <svg className={`w-3 h-3 transition-transform ${lmOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                                                                        </svg>
                                                                        Lettre de motivation
                                                                        <span className="flex-1 h-px bg-slate-200" />
                                                                    </button>
                                                                    {lmOpen && (
                                                                        <div className="mt-2">
                                                                            <LmDocxViewer emailId={email.id} fallback={email.generatedLm ?? ''} />
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </>
    )
}
