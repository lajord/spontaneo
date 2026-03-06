'use client'

import { useRef, useState } from 'react'

export type PreGenerateOptions = {
    userMailTemplate: string   // '' = template par défaut IA
    userMailSubject: string    // '' = sujet par défaut IA
    links: {
        linkedin: string
        github: string
        portfolio: string
        custom: { label: string; url: string }[]
    }
    extraFiles: File[]
}

const DEFAULT_OPTIONS: PreGenerateOptions = {
    userMailTemplate: '',
    userMailSubject: '',
    links: { linkedin: '', github: '', portfolio: '', custom: [] },
    extraFiles: [],
}

const TAGS = [
    "[nom de l'entreprise]",
    '[poste recherché]',
    '[nom du destinataire]',
    '[civilité]',
]

type Props = {
    open: boolean
    onConfirm: (opts: PreGenerateOptions) => void
    onCancel: () => void
}

export default function PreGenerateModal({ open, onConfirm, onCancel }: Props) {
    const [opts, setOpts] = useState<PreGenerateOptions>(DEFAULT_OPTIONS)
    const [useCustom, setUseCustom] = useState(false)
    const [error, setError] = useState('')
    const [dragging, setDragging] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const templateRef = useRef<HTMLTextAreaElement>(null)

    if (!open) return null

    // ── Template ───────────────────────────────────────────────────────────────

    function switchMode(custom: boolean) {
        setUseCustom(custom)
        setError('') // Clear any existing errors when switching modes
        if (!custom) {
            setOpts(prev => ({ ...prev, userMailTemplate: '', userMailSubject: '' }))
        } else {
            setOpts(prev => ({ ...prev, links: { linkedin: '', github: '', portfolio: '', custom: [] } }))
        }
    }

    function insertTag(tag: string) {
        const ta = templateRef.current
        if (!ta) return
        const start = ta.selectionStart
        const end = ta.selectionEnd
        const current = opts.userMailTemplate
        const next = current.slice(0, start) + tag + current.slice(end)
        setOpts(prev => ({ ...prev, userMailTemplate: next }))
        requestAnimationFrame(() => {
            ta.focus()
            ta.setSelectionRange(start + tag.length, start + tag.length)
        })
    }

    // ── Liens ──────────────────────────────────────────────────────────────────

    function setLink(key: 'linkedin' | 'github' | 'portfolio', value: string) {
        setOpts(prev => ({ ...prev, links: { ...prev.links, [key]: value } }))
    }

    function addCustomLink() {
        setOpts(prev => ({
            ...prev,
            links: { ...prev.links, custom: [...prev.links.custom, { label: '', url: '' }] },
        }))
    }

    function updateCustomLink(i: number, field: 'label' | 'url', value: string) {
        setOpts(prev => {
            const custom = prev.links.custom.map((c, idx) => idx === i ? { ...c, [field]: value } : c)
            return { ...prev, links: { ...prev.links, custom } }
        })
    }

    function removeCustomLink(i: number) {
        setOpts(prev => ({
            ...prev,
            links: { ...prev.links, custom: prev.links.custom.filter((_, idx) => idx !== i) },
        }))
    }

    // ── Fichiers ───────────────────────────────────────────────────────────────

    function addFiles(files: FileList | null) {
        if (!files) return
        setOpts(prev => ({ ...prev, extraFiles: [...prev.extraFiles, ...Array.from(files)] }))
    }

    function removeFile(i: number) {
        setOpts(prev => ({ ...prev, extraFiles: prev.extraFiles.filter((_, idx) => idx !== i) }))
    }

    function handleDrop(e: React.DragEvent) {
        e.preventDefault()
        setDragging(false)
        addFiles(e.dataTransfer.files)
    }

    // ── Rendu ──────────────────────────────────────────────────────────────────

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Overlay */}
            <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onCancel} />

            {/* Panel */}
            <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden flex flex-col max-h-[90vh] border border-slate-100">

                {/* Header */}
                <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/50">
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Personnaliser la campagne</h2>
                        <p className="text-sm text-slate-500 mt-1">Ces informations seront utilisées pour générer vos emails</p>
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

                {/* Scrollable body */}
                <div className="overflow-y-auto flex-1 px-8 py-8 space-y-8 bg-white">

                    {/* ── Section 1 : Template d'email ── */}
                    <section>
                        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">
                            Template d&apos;email
                        </h3>

                        {/* Sélection du mode */}
                        <div className="grid grid-cols-2 gap-3 mb-5">
                            <button
                                type="button"
                                onClick={() => switchMode(false)}
                                className={`text-left rounded-xl border-2 px-5 py-4 transition-colors ${!useCustom
                                    ? 'border-brand-500 bg-brand-50/50 shadow-sm'
                                    : 'border-slate-100 hover:border-slate-300 hover:bg-slate-50 bg-white'
                                    }`}
                            >
                                <div className="flex items-center gap-2.5">
                                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${!useCustom ? 'border-brand-500 bg-brand-500' : 'border-slate-300'}`}>
                                        {!useCustom && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                                    </div>
                                    <p className="text-sm font-semibold text-slate-900">Mail par défaut</p>
                                </div>
                            </button>

                            <button
                                type="button"
                                onClick={() => switchMode(true)}
                                className={`text-left rounded-xl border-2 px-5 py-4 transition-colors ${useCustom
                                    ? 'border-brand-500 bg-brand-50/50 shadow-sm'
                                    : 'border-slate-100 hover:border-slate-300 hover:bg-slate-50 bg-white'
                                    }`}
                            >
                                <div className="flex items-center gap-2.5">
                                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${useCustom ? 'border-brand-500 bg-brand-500' : 'border-slate-300'}`}>
                                        {useCustom && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                                    </div>
                                    <p className="text-sm font-semibold text-slate-900">Mail personnalisé</p>
                                </div>
                            </button>
                        </div>

                        {/* Éditeur — visible uniquement en mode personnalisé */}
                        {useCustom && (
                            <div className="space-y-4 border border-slate-200 rounded-xl p-5 bg-slate-50/50 shadow-inner">

                                {/* Explication du concept de crochets */}
                                <div className="flex gap-3 bg-white border border-brand-200 rounded-lg p-4 shadow-sm">
                                    <svg className="w-5 h-5 text-brand-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <div className="text-sm text-slate-700 leading-relaxed space-y-3">
                                        <p>Tout ce que vous écrivez entre <span className="font-mono font-bold text-brand-600">[ ]</span> est une <span className="font-semibold text-slate-900">instruction pour notre IA</span>. Elle lira votre consigne et rédigera le contenu correspondant, en se basant sur votre profil et les infos de l&apos;entreprise ciblée.</p>
                                        <div className="space-y-1.5 p-3 bg-slate-50 rounded text-slate-600">
                                            <p className="font-semibold text-slate-800 text-xs uppercase tracking-wide mb-2">Exemples d&apos;instructions :</p>
                                            <p className="font-mono text-xs bg-white border border-slate-200 rounded px-2.5 py-1.5 shadow-sm">[Explique en quoi mes compétences sont cohérentes avec cette entreprise]</p>
                                            <p className="font-mono text-xs bg-white border border-slate-200 rounded px-2.5 py-1.5 shadow-sm">[Dans cette partie, présente mon expérience la plus pertinente pour ce poste]</p>
                                        </div>
                                    </div>
                                </div>

                                {/* Objet du mail */}
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">
                                        Objet de l&apos;email
                                    </label>
                                    <div className="flex items-center bg-white border border-slate-200 rounded-lg px-3 focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-brand-500 transition-all shadow-sm">
                                        <span className="text-slate-400 font-mono text-sm shrink-0 mr-2 py-3 select-none">Objet:</span>
                                        <input
                                            type="text"
                                            value={opts.userMailSubject}
                                            onChange={e => setOpts(prev => ({ ...prev, userMailSubject: e.target.value }))}
                                            placeholder="Candidature spontanée — [poste recherché]"
                                            className="w-full text-sm placeholder:text-slate-400 focus:outline-none bg-transparent font-mono py-3"
                                        />
                                    </div>
                                </div>

                                {/* Salutation fixe */}
                                <div className="font-mono text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg px-4 py-3 select-none shadow-sm mt-4">
                                    Bonjour [civilité],
                                </div>

                                {/* Corps du mail */}
                                <div className="relative">
                                    <textarea
                                        ref={templateRef}
                                        value={opts.userMailTemplate}
                                        onChange={e => setOpts(prev => ({ ...prev, userMailTemplate: e.target.value }))}
                                        rows={8}
                                        placeholder={"Je m'appelle Matys, je suis étudiant en dernière année d'école d'ingénieur en informatique et je suis à la recherche d'un stage de 6 mois à partir d'avril.\n\nJe suis très intéressé de pouvoir avoir l'opportunité de travailler chez [nom de l'entreprise] en tant qu'Ingénieur IA.\n\nJ'ai pu [parler de mes expériences les plus pertinentes qui pourraient matcher avec cette entreprise]..."}
                                        className="w-full border border-slate-200 rounded-lg p-4 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition resize-none bg-white font-mono shadow-sm leading-relaxed"
                                    />
                                </div>

                                {/* Chips — suggestions d'instructions fréquentes */}
                                <div>
                                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2.5">Variables rapides :</p>
                                    <div className="flex flex-wrap gap-2">
                                        {TAGS.map(tag => (
                                            <button
                                                key={tag}
                                                type="button"
                                                onClick={() => insertTag(tag)}
                                                className="text-xs bg-white border border-slate-200 hover:border-brand-500 hover:bg-brand-50 hover:text-brand-700 text-slate-600 rounded-lg px-3 py-1.5 transition-all shadow-sm font-mono font-medium"
                                            >
                                                {tag}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                    </section>

                    {/* ── Section 2 : Liens (template auto uniquement) ── */}
                    {!useCustom && (
                        <section className="pt-2">
                            <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-2 border-b border-slate-100 pb-2">
                                Liens additionnels
                            </h3>
                            <p className="text-sm text-slate-500 mb-5">
                                Ces liens seront ajoutés automatiquement à la fin du mail généré pour inciter les recruteurs à en voir plus sur vous.
                            </p>
                            <div className="space-y-3 pl-1">
                                <div className="flex items-center gap-4">
                                    <span className="w-24 text-sm font-medium text-slate-600 shrink-0">LinkedIn</span>
                                    <input
                                        type="url"
                                        placeholder="https://linkedin.com/in/votre-profil"
                                        value={opts.links.linkedin}
                                        onChange={e => setLink('linkedin', e.target.value)}
                                        className="flex-1 text-sm border border-slate-200 rounded-lg px-3.5 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm transition"
                                    />
                                </div>
                                <div className="flex items-center gap-4">
                                    <span className="w-24 text-sm font-medium text-slate-600 shrink-0">GitHub</span>
                                    <input
                                        type="url"
                                        placeholder="https://github.com/votre-profil"
                                        value={opts.links.github}
                                        onChange={e => setLink('github', e.target.value)}
                                        className="flex-1 text-sm border border-slate-200 rounded-lg px-3.5 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm transition"
                                    />
                                </div>
                                <div className="flex items-center gap-4">
                                    <span className="w-24 text-sm font-medium text-slate-600 shrink-0">Portfolio</span>
                                    <input
                                        type="url"
                                        placeholder="https://mon-portfolio.fr"
                                        value={opts.links.portfolio}
                                        onChange={e => setLink('portfolio', e.target.value)}
                                        className="flex-1 text-sm border border-slate-200 rounded-lg px-3.5 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm transition"
                                    />
                                </div>

                                {opts.links.custom.map((c, i) => (
                                    <div key={i} className="flex items-center gap-3 mt-4">
                                        <input
                                            type="text"
                                            placeholder="Libellé (ex: Behance)"
                                            value={c.label}
                                            onChange={e => updateCustomLink(i, 'label', e.target.value)}
                                            className="w-32 text-sm border border-slate-200 rounded-lg px-3.5 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm transition"
                                        />
                                        <input
                                            type="url"
                                            placeholder="https://..."
                                            value={c.url}
                                            onChange={e => updateCustomLink(i, 'url', e.target.value)}
                                            className="flex-1 text-sm border border-slate-200 rounded-lg px-3.5 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm transition"
                                        />
                                        <button
                                            onClick={() => removeCustomLink(i)}
                                            className="w-8 h-8 rounded-full bg-red-50 hover:bg-red-100 text-red-500 flex items-center justify-center transition-colors shrink-0"
                                            title="Supprimer ce lien"
                                        >
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                                            </svg>
                                        </button>
                                    </div>
                                ))}

                                <button
                                    onClick={addCustomLink}
                                    className="text-sm text-brand-600 hover:text-brand-800 font-medium flex items-center gap-1.5 transition-colors mt-4 bg-brand-50 px-3 py-1.5 rounded-md hover:bg-brand-100 w-fit"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                                    </svg>
                                    Ajouter un lien personnalisé
                                </button>
                            </div>
                        </section>
                    )}

                    {/* ── Section 3 : Pièces jointes ── */}
                    <section className="pt-2">
                        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">
                            Pièces jointes additionnelles
                        </h3>
                        <p className="text-sm text-slate-500 mb-4">
                            Ces documents seront joints aux emails envoyés (en plus du CV).
                        </p>
                        <div
                            onDragOver={e => { e.preventDefault(); setDragging(true) }}
                            onDragLeave={() => setDragging(false)}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            className={`border-2 border-dashed rounded-xl px-5 py-6 text-center cursor-pointer transition-colors ${dragging ? 'border-brand-400 bg-brand-50' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                                }`}
                        >
                            <svg className="w-8 h-8 text-slate-400 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                            </svg>
                            <p className="text-sm font-medium text-slate-600">
                                Glisser-déposer ou <span className="text-brand-600">parcourir</span>
                            </p>
                            <p className="text-xs text-slate-500 mt-1">PDF, DOCX — ex: Portfolio, Certifications</p>
                            <input
                                ref={fileInputRef}
                                type="file"
                                multiple
                                accept=".pdf,.docx"
                                className="hidden"
                                onChange={e => addFiles(e.target.files)}
                            />
                        </div>

                        {opts.extraFiles.length > 0 && (
                            <ul className="mt-2.5 space-y-1.5">
                                {opts.extraFiles.map((f, i) => (
                                    <li key={i} className="flex items-center justify-between gap-2 bg-slate-50 rounded-lg px-3 py-2">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                            </svg>
                                            <span className="text-xs text-slate-600 truncate font-medium">{f.name}</span>
                                            <span className="text-xs text-slate-400 shrink-0">
                                                {(f.size / 1024).toFixed(0)} Ko
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => removeFile(i)}
                                            className="w-5 h-5 rounded-full bg-red-50 text-red-400 hover:bg-red-100 flex items-center justify-center transition-colors shrink-0"
                                        >
                                            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                                            </svg>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                </div>

                {/* Footer */}
                <div className="px-8 py-5 border-t border-slate-100 flex items-center justify-between shrink-0 bg-slate-50/50">
                    <div className="flex-1">
                        {error && <p className="text-sm text-red-500 font-medium">{error}</p>}
                    </div>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={onCancel}
                            className="text-sm text-slate-600 hover:text-slate-900 font-medium px-5 py-2.5 rounded-lg hover:bg-slate-200/60 border border-transparent transition-colors"
                        >
                            Annuler
                        </button>
                        <button
                            onClick={() => {
                                if (useCustom) {
                                    if (!opts.userMailSubject.trim() || !opts.userMailTemplate.trim()) {
                                        setError('Veuillez remplir l\'objet et le corps de l\'email.')
                                        return
                                    }
                                }
                                setError('')
                                onConfirm(opts)
                            }}
                            className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 shadow border border-brand-500 text-white text-sm font-semibold px-6 py-2.5 rounded-lg transition-transform hover:-translate-y-px active:translate-y-0"
                        >
                            Générer les emails
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
