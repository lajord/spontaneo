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
    block: GeneratedBlock
    campaignName: string
    onBack: () => void
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
                    inWrapper: false,
                    ignoreWidth: false,
                    ignoreHeight: false,
                    ignoreFonts: false,
                    breakPages: false,
                    useBase64URL: true,
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
            <pre className="mt-2 text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed bg-slate-50 rounded-lg px-3.5 py-3">
                {fallback}
            </pre>
        )
    }

    return (
        <div className="mt-2 relative">
            {status === 'loading' && (
                <div className="px-4 py-6 text-sm text-slate-600 text-center bg-slate-50 rounded-lg">
                    Chargement de la lettre…
                </div>
            )}
            <div
                ref={containerRef}
                className={`docx-preview-container bg-white rounded-lg border border-slate-300 overflow-auto ${status === 'loading' ? 'hidden' : ''}`}
                style={{ maxHeight: '600px' }}
            />
            {status === 'ok' && (
                <a
                    href={`/api/emails/${emailId}/lm`}
                    download="lettre-motivation.docx"
                    className="mt-2 inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-700 transition-colors"
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

export default function CompanyDetailView({ block, campaignName, onBack }: Props) {
    const [expandedEmail, setExpandedEmail] = useState<string | null>(null)
    const [expandedLm, setExpandedLm] = useState<Set<string>>(new Set())

    const draftEmails = block.emails.filter(e => e.status === 'draft')
    const { enriched } = block

    function toggleLm(emailId: string) {
        setExpandedLm(prev => {
            const next = new Set(prev)
            next.has(emailId) ? next.delete(emailId) : next.add(emailId)
            return next
        })
    }

    const resultats = enriched?.resultats ?? []

    return (
        <div className="flex flex-col h-full">

            {/* ── Fil d'Ariane ─────────────────────────────────────────────── */}
            <div className="px-6 py-3 border-b border-slate-300 flex items-center gap-2 shrink-0 bg-slate-50/60">
                <button
                    onClick={onBack}
                    className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-700 transition-colors group"
                >
                    <svg className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                    </svg>
                    Retour
                </button>
                <span className="text-slate-200">/</span>
                <span className="text-xs text-slate-600 truncate max-w-[140px]">{campaignName}</span>
                <span className="text-slate-200">/</span>
                <span className="text-xs font-medium text-slate-700 truncate">{block.companyName}</span>
            </div>

            {/* ── Contenu scrollable ────────────────────────────────────────── */}
            <div className="flex-1 overflow-y-auto">

                {/* En-tête entreprise */}
                <div className="px-8 pt-6 pb-5 border-b border-slate-200">
                    <h2 className="text-base font-bold text-slate-900 leading-tight">{block.companyName}</h2>
                    {block.companyAddress && (
                        <span className="flex items-center gap-1 text-xs text-slate-600 mt-1.5">
                            <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            {block.companyAddress}
                        </span>
                    )}
                </div>

                {/* ── Contacts enrichis ─────────────────────────────────────── */}
                {resultats.length > 0 && (
                    <div className="px-8 py-5 border-b border-slate-200">
                        <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Contacts trouvés</p>
                        <div className="space-y-2">
                            {resultats.map((contact, idx) => {
                                const name = [contact.prenom, contact.nom].filter(Boolean).join(' ')
                                return (
                                    <div key={idx} className="flex items-start gap-3">
                                        <span className="text-xs font-medium text-slate-600 w-20 shrink-0 pt-0.5">
                                            {contact.type === 'specialise' ? (contact.role ?? 'Contact') : 'Général'}
                                        </span>
                                        <div className="flex flex-col gap-0.5">
                                            {name && <span className="text-sm text-slate-800">{name}</span>}
                                            {contact.mail && (
                                                <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded font-mono w-fit">
                                                    {contact.mail}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )}

                {/* ── Emails générés ────────────────────────────────────────── */}
                <div className="px-8 py-5">
                    <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">
                        Emails générés
                        <span className="ml-1.5 normal-case font-normal">({draftEmails.length} en attente)</span>
                    </p>

                    {draftEmails.length === 0 ? (
                        <p className="text-sm text-slate-600 py-4 text-center">Aucun email en attente</p>
                    ) : (
                        <div className="space-y-3">
                            {draftEmails.map((email, idx) => {
                                const isOpen = expandedEmail === email.id
                                const lmOpen = expandedLm.has(email.id)
                                return (
                                    <div key={email.id} className="border border-slate-300 rounded-xl overflow-hidden bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">

                                        {/* Header email */}
                                        <div
                                            className="px-5 py-4 flex items-center justify-between gap-3 cursor-pointer hover:bg-slate-50/70 transition-colors"
                                            onClick={() => setExpandedEmail(isOpen ? null : email.id)}
                                        >
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-xs font-semibold text-slate-600">#{idx + 1}</span>
                                                    <span className="text-sm font-medium text-slate-800">
                                                        {email.recipientName ?? 'Destinataire'}
                                                    </span>
                                                    {email.to && (
                                                        <span className="text-xs text-slate-600 font-mono truncate">{email.to}</span>
                                                    )}
                                                </div>
                                                <p className="text-xs text-slate-600 truncate pl-5">{email.subject}</p>
                                            </div>
                                            <svg
                                                className={`w-3.5 h-3.5 text-slate-500 transition-transform shrink-0 ${isOpen ? 'rotate-180' : ''}`}
                                                fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                            >
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                            </svg>
                                        </div>

                                        {/* Corps déplié */}
                                        {isOpen && (
                                            <div className="border-t border-slate-200 px-5 pb-5 pt-4 space-y-4">

                                                <div>
                                                    <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">Objet</p>
                                                    <p className="text-sm text-slate-800 bg-slate-50 rounded-lg px-3.5 py-2.5">{email.subject}</p>
                                                </div>

                                                <div>
                                                    <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">Corps du mail</p>
                                                    <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed bg-slate-50 rounded-lg px-3.5 py-3">
                                                        {email.body}
                                                    </pre>
                                                </div>

                                                {email.generatedLm && (
                                                    <div>
                                                        <button
                                                            onClick={() => toggleLm(email.id)}
                                                            className="flex items-center gap-2 text-xs font-semibold text-slate-600 uppercase tracking-wide hover:text-slate-600 transition-colors w-full py-1"
                                                        >
                                                            <svg
                                                                className={`w-3 h-3 transition-transform ${lmOpen ? 'rotate-180' : ''}`}
                                                                fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                                            >
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                                                            </svg>
                                                            Lettre de motivation
                                                            <span className="flex-1 h-px bg-slate-100" />
                                                        </button>
                                                        {lmOpen && (
                                                            <LmDocxViewer
                                                                emailId={email.id}
                                                                fallback={email.generatedLm ?? ''}
                                                            />
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
        </div>
    )
}
