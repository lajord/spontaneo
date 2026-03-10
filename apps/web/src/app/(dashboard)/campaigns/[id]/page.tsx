'use client'

import { useEffect, useRef, useState, useCallback, Fragment } from 'react'
import { useRouter } from 'next/navigation'
import LaunchModal from './LaunchModal'
import CompanyDetailView from './CompanyDetailView'
import PreGenerateModal, { type PreGenerateOptions } from './PreGenerateModal'
import SelectCompaniesModal from './SelectCompaniesModal'

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

type Company = {
  id: string
  name: string
  address: string | null
  website: string | null
  phone: string | null
  siren: string | null
  source: string | null
  status: string
  enriched: EnrichedData | null
}

type Campaign = {
  id: string
  name: string
  jobTitle: string
  location: string
  status: string
  dailyLimit: number | null
  sendStartHour: number | null
  sendEndHour: number | null
  totalEmails: number | null
  sentCount: number
  launchedAt: string | null
}

type GeneratedBlock = {
  companyId: string
  companyName: string
  companyAddress: string | null
  enriched: EnrichedData
  emails: EmailRecipient[]
}

type CompanyProcessing = {
  companyId: string
  companyName: string
  state: 'enriching' | 'generating'
}

type FlatEmail = EmailRecipient & { companyName: string }

type Tab = 'apercu' | 'en_cours' | 'en_attente' | 'envoyes'

export default function CampaignPage({ params }: { params: { id: string } }) {
  const { id } = params
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [scraping, setScraping] = useState(false)
  const [scrapePhase, setScrapePhase] = useState<'recherche' | 'filtrage'>('recherche')
  const scrapePhaseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const hasAutoScraped = useRef(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  // Mutable ref so connectToJob always captures fresh state without stale closures
  const connectToJobRef = useRef<(jobId: string) => void>(() => { })

  const [generating, setGenerating] = useState(false)
  const [blocks, setBlocks] = useState<GeneratedBlock[]>([])
  const [processingMap, setProcessingMap] = useState<Map<string, CompanyProcessing>>(new Map())
  const [expandedEmail, setExpandedEmail] = useState<string | null>(null)
  const [expandedLm, setExpandedLm] = useState<Set<string>>(new Set())
  const [sending, setSending] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('apercu')
  const [openTabs, setOpenTabs] = useState<Set<Tab>>(new Set<Tab>(['apercu']))
  const [launchModalOpen, setLaunchModalOpen] = useState(false)
  const [hoveringStop, setHoveringStop] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null)
  const [selectCompaniesOpen, setSelectCompaniesOpen] = useState(false)
  const [preGenerateOpen, setPreGenerateOpen] = useState(false)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const router = useRouter()

  function openTab(tab: Tab) {
    setOpenTabs(prev => new Set<Tab>(Array.from(prev).concat(tab)))
    setActiveTab(tab)
    setSelectedCompanyId(null)
  }

  function switchTab(tab: Tab) {
    setActiveTab(tab)
    setSelectedCompanyId(null)
  }

  function closeTab(tab: Tab, e: React.MouseEvent) {
    e.stopPropagation()
    setOpenTabs(prev => { const s = new Set<Tab>(Array.from(prev)); s.delete(tab); return s })
    if (activeTab === tab) setActiveTab('apercu')
  }

  const loadEmails = useCallback((emails: Array<{
    id: string; subject: string; body: string; to: string | null; recipientName: string | null; generatedLm: string | null; status: string; sentAt?: string | null; companyId: string;
    company: { name: string; address: string | null; enriched: EnrichedData | null }
  }>) => {
    if (!Array.isArray(emails) || emails.length === 0) return
    const map = new Map<string, GeneratedBlock>()
    for (const email of emails) {
      if (!map.has(email.companyId)) {
        map.set(email.companyId, {
          companyId: email.companyId,
          companyName: email.company.name,
          companyAddress: email.company.address ?? null,
          enriched: email.company.enriched ?? { resultats: [] },
          emails: [],
        })
      }
      map.get(email.companyId)!.emails.push({
        id: email.id,
        subject: email.subject,
        body: email.body,
        to: email.to ?? null,
        recipientName: email.recipientName ?? null,
        generatedLm: email.generatedLm ?? null,
        status: email.status,
        sentAt: email.sentAt ?? null,
      })
    }
    const restored = Array.from(map.values())
    if (restored.length > 0) {
      setBlocks(restored)
      setOpenTabs(new Set<Tab>(['apercu', 'en_cours', 'en_attente', 'envoyes']))
    }
  }, [])

  const refreshEmails = useCallback(() => {
    fetch(`/api/campaigns/${id}/emails`).then(r => r.json()).then(loadEmails)
    fetch(`/api/campaigns/${id}`).then(r => r.json()).then(setCampaign)
  }, [id, loadEmails])

  useEffect(() => {
    fetch(`/api/campaigns/${id}`).then(r => r.json()).then(setCampaign)
    fetch(`/api/campaigns/${id}/companies`).then(r => r.json()).then(data => {
      setCompanies(Array.isArray(data) ? data : [])
    })
    fetch(`/api/campaigns/${id}/emails`).then(r => r.json()).then(loadEmails)
  }, [id, loadEmails])

  // Mise à jour du callback mutable à chaque render pour éviter les closures périmées
  connectToJobRef.current = (jobId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    const es = new EventSource(`/api/jobs/${jobId}/events`)
    eventSourceRef.current = es

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (event.type === 'enriching') {
          setProcessingMap(prev => new Map(prev).set(event.companyId, { companyId: event.companyId, companyName: event.companyName, state: 'enriching' }))
        } else if (event.type === 'generating') {
          setProcessingMap(prev => {
            const next = new Map(prev)
            const existing = next.get(event.companyId)
            if (existing) next.set(event.companyId, { ...existing, state: 'generating' })
            return next
          })
        } else if (event.type === 'done') {
          setBlocks(prev => [...prev, event as GeneratedBlock])
          setProcessingMap(prev => { const next = new Map(prev); next.delete(event.companyId); return next })
        } else if (event.type === 'complete') {
          setCampaign(prev => prev ? { ...prev, status: 'emails_generated' } : prev)
          setGenerating(false)
          setProcessingMap(new Map())
          es.close()
          eventSourceRef.current = null
          if (openTabs.has('en_attente')) setActiveTab('en_attente')
          else setActiveTab('apercu')
        } else if (event.type === 'error') {
          setMessage(event.message ?? 'Erreur')
          setGenerating(false)
          es.close()
          eventSourceRef.current = null
        }
      } catch { /* SSE malformée */ }
    }
  }

  // Nettoyage à la destruction du composant
  useEffect(() => {
    return () => { eventSourceRef.current?.close() }
  }, [])

  // Auto-reconnexion si le job tourne en background (user revient sur la page)
  useEffect(() => {
    if (campaign?.status !== 'generating' || generating) return
    fetch(`/api/campaigns/${id}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.jobId) {
          setGenerating(true)
          setOpenTabs(new Set<Tab>(['apercu', 'en_cours', 'en_attente', 'envoyes']))
          setActiveTab('en_cours')
          connectToJobRef.current(data.jobId)
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign?.status])

  // Polling quand la campagne est active
  useEffect(() => {
    if (campaign?.status !== 'active') return
    const interval = setInterval(refreshEmails, 30000)
    return () => clearInterval(interval)
  }, [campaign?.status, refreshEmails])

  useEffect(() => {
    if (campaign?.status === 'draft' && !hasAutoScraped.current) {
      hasAutoScraped.current = true
      handleScrape()
    }
  }, [campaign])

  async function handleScrape() {
    setScraping(true)
    setScrapePhase('recherche')
    setMessage('')
    // Après 20s, on passe en phase "filtrage" (le filtre IA prend le relais)
    scrapePhaseTimer.current = setTimeout(() => setScrapePhase('filtrage'), 20_000)
    const res = await fetch(`/api/campaigns/${id}/scrape`, { method: 'POST' })
    if (scrapePhaseTimer.current) clearTimeout(scrapePhaseTimer.current)
    const data = await res.json()
    if (res.ok) setCompanies(data.companies ?? [])
    else setMessage(data.error ?? 'Erreur lors de la recherche')
    setScraping(false)
  }



  async function handleDeleteCompany(companyId: string) {
    setDeletingId(companyId)
    const res = await fetch(`/api/campaigns/${id}/companies/${companyId}`, { method: 'DELETE' })
    if (res.ok) setCompanies(prev => prev.filter(c => c.id !== companyId))
    setDeletingId(null)
  }

  async function handleGenerate(opts: PreGenerateOptions) {
    setPreGenerateOpen(false)
    setGenerating(true)
    setBlocks([])
    setMessage('')
    setProcessingMap(new Map())
    setOpenTabs(new Set<Tab>(['apercu', 'en_cours', 'en_attente', 'envoyes']))
    setActiveTab('en_cours')

    // 1. Uploader les pièces jointes supplémentaires si présentes
    if (opts.extraFiles.length > 0) {
      const formData = new FormData()
      for (const f of opts.extraFiles) formData.append('files', f)
      await fetch(`/api/campaigns/${id}/attachments`, { method: 'POST', body: formData })
    }

    // 2. Enqueuer le job — retourne { jobId } (JSON, plus de SSE inline)
    const res = await fetch(`/api/campaigns/${id}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        links: opts.links,
        userMailTemplate: opts.userMailTemplate || null,
        userMailSubject: opts.userMailSubject || null,
      }),
    })
    if (!res.ok) {
      setMessage('Erreur lors du lancement de la génération')
      setGenerating(false)
      return
    }

    const { jobId } = await res.json()
    if (!jobId) {
      setMessage('Erreur : aucun job ID reçu')
      setGenerating(false)
      return
    }

    // 3. Ouvrir le stream SSE de suivi (avec replay Last-Event-ID si reconnexion)
    connectToJobRef.current(jobId)
  }

  async function sendEmail(emailId: string) {
    setSending(emailId)
    const res = await fetch(`/api/emails/${emailId}/send`, { method: 'POST' })
    const data = await res.json()
    if (res.ok) {
      setBlocks(prev => prev.map(b => ({
        ...b,
        emails: b.emails.map(e => e.id === emailId ? { ...e, status: 'sent' } : e),
      })))
    } else {
      setMessage(data.error ?? "Erreur d'envoi")
    }
    setSending(null)
  }

  async function handleStop() {
    const res = await fetch(`/api/campaigns/${id}/launch`, { method: 'DELETE' })
    if (res.ok) {
      setCampaign(prev => prev ? { ...prev, status: 'paused' } : prev)
      setHoveringStop(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    const res = await fetch(`/api/campaigns/${id}`, { method: 'DELETE' })
    if (res.ok) {
      router.push('/dashboard')
    } else {
      setDeleting(false)
    }
  }

  function handleLaunchSuccess() {
    setLaunchModalOpen(false)
    // Recharge la campagne pour obtenir le nouveau statut + champs
    fetch(`/api/campaigns/${id}`).then(r => r.json()).then(setCampaign)
  }

  const isLaunched = campaign?.status === 'active' || campaign?.status === 'paused' || campaign?.status === 'finished'
  const isGenerationView = generating || blocks.length > 0
  const doneIds = new Set(blocks.map(b => b.companyId))
  const queuedCompanies = companies.filter(c => !doneIds.has(c.id) && !processingMap.has(c.id))
  const allEmails: FlatEmail[] = blocks.flatMap(b => b.emails.map(e => ({ ...e, companyName: b.companyName })))
  const draftEmails = allEmails.filter(e => e.status === 'draft')
  const sentEmails = allEmails.filter(e => e.status === 'sent').sort((a, b) =>
    (b.sentAt ?? '').localeCompare(a.sentAt ?? '')
  )
  const filteredCompanies = companies.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.address ?? '').toLowerCase().includes(search.toLowerCase())
  )
  const filteredHiringCompanies = filteredCompanies.filter(c => c.source === 'apollo_jobtitle')
  const filteredPotentialCompanies = filteredCompanies.filter(c => c.source !== 'apollo_jobtitle')
  const sortedFilteredCompanies = [...filteredHiringCompanies, ...filteredPotentialCompanies]
  const hasHiringSplit = filteredHiringCompanies.length > 0 && filteredPotentialCompanies.length > 0

  // Calcul "temps avant prochain envoi"
  function nextSendLabel(): string {
    if (!campaign?.dailyLimit) return ''
    const intervalMin = Math.floor(1440 / campaign.dailyLimit)
    const lastSentEmail = sentEmails[0]
    if (!lastSentEmail?.sentAt) return 'dans les prochaines minutes'
    const elapsed = (Date.now() - new Date(lastSentEmail.sentAt).getTime()) / 60000
    const remaining = Math.max(0, Math.ceil(intervalMin - elapsed))
    return remaining <= 1 ? 'imminent' : `dans ~${remaining} min`
  }

  function fmtHour(h: number | null) {
    if (h === null) return ''
    return `${String(h).padStart(2, '0')}h`
  }

  type TabDef = { id: Tab; label: string; count?: number; pulse?: boolean; closeable?: boolean }
  const allTabDefs: TabDef[] = [
    { id: 'apercu' as Tab, label: campaign?.name ?? 'Campagne' },
    { id: 'en_cours' as Tab, label: 'En cours', count: queuedCompanies.length + processingMap.size || undefined, pulse: generating, closeable: true },
    { id: 'en_attente' as Tab, label: 'En attente', count: draftEmails.length || undefined, closeable: true },
    { id: 'envoyes' as Tab, label: 'Envoyés', count: sentEmails.length || undefined, closeable: true },
  ]
  const tabDefs = allTabDefs.filter(t => openTabs.has(t.id))

  if (!campaign) {
    return (
      <div className="flex flex-col h-full bg-slate-100">
        <div className="flex-1 bg-white flex items-center justify-center">
          <p className="text-sm text-slate-400">Chargement...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">

      {/* ── Barre d'onglets style navigateur ───────────────────────────────── */}
      <div className="border-b border-slate-200 px-3 pt-2 flex items-end gap-0 shrink-0" style={{ backgroundColor: '#F3F4F0' }}>
        {tabDefs.map(tab => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => switchTab(tab.id)}
              className={[
                'relative flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-t-lg border-x border-t transition-all select-none w-44 justify-center overflow-hidden whitespace-nowrap',
                isActive
                  ? 'bg-white border-slate-200 text-slate-900 font-medium -mb-px z-10 shadow-[0_1px_0_white]'
                  : 'border-transparent text-slate-500 hover:bg-white/60 hover:text-slate-700',
              ].join(' ')}
            >
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${isActive ? 'bg-slate-100 text-slate-600' : 'bg-slate-200/80 text-slate-400'}`}>
                  {tab.count}
                </span>
              )}
              {tab.pulse && (
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
              )}
              {tab.closeable && (
                <span
                  role="button"
                  onClick={e => closeTab(tab.id, e)}
                  className={`flex items-center justify-center w-4 h-4 rounded hover:bg-black/10 transition-colors text-slate-400 hover:text-slate-700`}
                >
                  <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* ── Zone de contenu ─────────────────────────────────────────────────── */}
      <div className="flex-1 bg-white overflow-y-auto">

        {/* APERÇU */}
        {activeTab === 'apercu' && (
          <div>
            {/* En-tête campagne */}
            <div className="px-8 py-6 border-b border-slate-50 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h1 className="text-lg font-bold text-slate-900">{campaign.name}</h1>
                  {/* Badge statut */}
                  {campaign.status === 'active' && (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      En cours
                    </span>
                  )}
                  {campaign.status === 'paused' && (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                      ⏸ En pause
                    </span>
                  )}
                  {campaign.status === 'finished' && (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
                      ✓ Terminée
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-400 mt-0.5">{campaign.jobTitle} · {campaign.location}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {/* Bouton Étape suivante (pré-génération) */}
                {!isGenerationView && companies.length > 0 && (
                  <button
                    onClick={() => setSelectCompaniesOpen(true)}
                    disabled={scraping}
                    className="inline-flex items-center gap-1.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                  >
                    Étape suivante →
                  </button>
                )}

                {/* Bouton Lancer / Stopper / Relancer */}
                {isGenerationView && campaign.status !== 'active' && campaign.status !== 'paused' && campaign.status !== 'finished' && (
                  <button
                    onClick={() => setLaunchModalOpen(true)}
                    disabled={generating || draftEmails.length === 0}
                    className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
                  >
                    Lancer la campagne
                  </button>
                )}

                {campaign.status === 'active' && (
                  <button
                    onMouseEnter={() => setHoveringStop(true)}
                    onMouseLeave={() => setHoveringStop(false)}
                    onClick={handleStop}
                    className={`inline-flex items-center gap-1.5 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all ${hoveringStop
                      ? 'bg-red-500 hover:bg-red-600'
                      : 'bg-emerald-500 hover:bg-emerald-600'
                      }`}
                  >
                    {hoveringStop ? 'Stopper la campagne' : '● Campagne lancée'}
                  </button>
                )}

                {campaign.status === 'paused' && (
                  <>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      className="inline-flex items-center gap-1.5 border border-red-200 text-red-500 hover:bg-red-50 disabled:opacity-40 text-sm font-medium px-3 py-2 rounded-lg transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Supprimer
                    </button>
                    <button
                      onClick={() => setLaunchModalOpen(true)}
                      className="inline-flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
                    >
                      ↺ Reprendre
                    </button>
                  </>
                )}

                {campaign.status === 'finished' && (
                  <>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      className="inline-flex items-center gap-1.5 border border-red-200 text-red-500 hover:bg-red-50 disabled:opacity-40 text-sm font-medium px-3 py-2 rounded-lg transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Supprimer
                    </button>
                    <span className="inline-flex items-center gap-1.5 bg-slate-100 text-slate-500 text-sm font-medium px-4 py-2 rounded-lg">
                      ✓ Campagne terminée
                    </span>
                  </>
                )}


              </div>
            </div>

            {message && (
              <div className="px-8 py-3 border-b border-slate-50">
                <p className="text-sm text-slate-600 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">{message}</p>
              </div>
            )}

            {/* ── Vue campagne active / paused / finished ── */}
            {isLaunched && (
              <div>
                {/* Stats */}
                <div className="px-8 py-5 border-b border-slate-50 space-y-4">
                  {/* Barre de progression */}
                  {campaign.totalEmails !== null && campaign.totalEmails > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-medium text-slate-500">Progression</span>
                        <span className="text-xs font-bold text-slate-900">
                          {campaign.sentCount} / {campaign.totalEmails} mails
                        </span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(100, (campaign.sentCount / campaign.totalEmails) * 100)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Infos */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-50 rounded-xl px-4 py-3">
                      <p className="text-xs text-slate-400 mb-0.5">Restants</p>
                      <p className="text-lg font-bold text-slate-900">{(campaign.totalEmails ?? 0) - campaign.sentCount}</p>
                    </div>
                    <div className="bg-slate-50 rounded-xl px-4 py-3">
                      <p className="text-xs text-slate-400 mb-0.5">Limite / jour</p>
                      <p className="text-lg font-bold text-slate-900">{campaign.dailyLimit ?? '—'}</p>
                    </div>
                    <div className="bg-slate-50 rounded-xl px-4 py-3">
                      <p className="text-xs text-slate-400 mb-0.5">Fenêtre d&apos;envoi</p>
                      <p className="text-sm font-semibold text-slate-900">{fmtHour(campaign.sendStartHour)} – {fmtHour(campaign.sendEndHour)}</p>
                    </div>
                    {campaign.status === 'active' && (
                      <div className="bg-slate-50 rounded-xl px-4 py-3">
                        <p className="text-xs text-slate-400 mb-0.5">Prochain envoi</p>
                        <p className="text-sm font-semibold text-slate-900">{nextSendLabel()}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Liste des mails envoyés */}
                <div className="px-8 py-4">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">
                    Mails envoyés
                    {sentEmails.length > 0 && <span className="ml-1.5 text-slate-400">({sentEmails.length})</span>}
                  </p>
                  {sentEmails.length === 0 ? (
                    <div className="py-10 text-center">
                      <p className="text-sm text-slate-400">
                        {campaign.status === 'active'
                          ? 'Premier envoi imminent...'
                          : 'Aucun mail envoyé'}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {sentEmails.map(email => (
                        <div key={email.id} className="flex items-center justify-between gap-3 py-2.5 border-b border-slate-50 last:border-0">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-slate-800 truncate">{email.companyName}</p>
                            <p className="text-xs text-slate-400 truncate">
                              {email.recipientName && <span className="mr-1.5">{email.recipientName}</span>}
                              {email.to && <span className="font-mono">{email.to}</span>}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {email.sentAt && (
                              <span className="text-xs text-slate-400">
                                {new Date(email.sentAt).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                            <span className="text-xs bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-medium">Envoyé</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Vue pré-lancement (stats génération) ── */}
            {!isLaunched && isGenerationView && (
              <div className="px-8 py-4 border-b border-slate-50 space-y-0">
                {([
                  { label: 'Entreprises trouvées', value: companies.length, tab: null as Tab | null },
                  { label: 'Enrichissements / Rédaction en cours', value: queuedCompanies.length + processingMap.size, tab: 'en_cours' as Tab },
                  { label: 'Mails en attente d\'envoi', value: draftEmails.length, tab: 'en_attente' as Tab },
                  { label: 'Mails envoyés', value: sentEmails.length, tab: 'envoyes' as Tab },
                ]).map(row => (
                  <div key={row.label} className="flex items-center justify-between py-3 border-b border-slate-50 last:border-0">
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-bold text-slate-900 w-8 text-right">{row.value}</span>
                      <span className="text-sm text-slate-500">{row.label}</span>
                    </div>
                    {row.tab && !openTabs.has(row.tab) && (
                      <button
                        onClick={() => openTab(row.tab!)}
                        className="text-xs text-brand-500 hover:text-brand-600 font-medium hover:underline transition-colors"
                      >
                        Voir →
                      </button>
                    )}
                    {row.tab && openTabs.has(row.tab) && (
                      <button
                        onClick={() => setActiveTab(row.tab!)}
                        className="text-xs text-slate-400 hover:text-slate-600 font-medium hover:underline transition-colors"
                      >
                        Ouvrir
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Chargement */}
            {!isGenerationView && companies.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24">
                {scraping ? (
                  <>
                    <span className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin mb-3" />
                    <p className="text-sm text-slate-500 font-medium">
                      {scrapePhase === 'filtrage' ? 'Filtrage des entreprises...' : 'Récupération des entreprises...'}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">Cela peut prendre quelques minutes</p>
                  </>
                ) : (
                  <p className="text-sm text-slate-400">Aucune entreprise trouvée.</p>
                )}
              </div>
            )}

            {/* Barre recherche + liste entreprises (pré-génération) */}
            {!isLaunched && companies.length > 0 && (
              <>
                <div className="px-8 py-3 border-b border-slate-50 flex items-center justify-between gap-4 sticky top-0 bg-white z-10">
                  <p className="text-xs font-medium text-slate-500">
                    {isGenerationView
                      ? `${blocks.length} / ${companies.length} entreprise${companies.length !== 1 ? 's' : ''} traitée${blocks.length !== 1 ? 's' : ''}`
                      : `${companies.length} entreprise${companies.length !== 1 ? 's' : ''} trouvée${companies.length !== 1 ? 's' : ''}`
                    }
                  </p>
                  <div className="flex items-center gap-3">
                    {!isGenerationView && (
                      <div className="flex items-center bg-slate-100/80 p-1 rounded-lg border border-slate-200/50">
                        <button
                          onClick={() => setViewMode('grid')}
                          className={`p-1.5 rounded-md transition-all ${viewMode === 'grid' ? 'bg-white shadow-sm text-brand-600' : 'text-slate-400 hover:text-slate-600'}`}
                          title="Vue en grille"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                        </button>
                        <button
                          onClick={() => setViewMode('list')}
                          className={`p-1.5 rounded-md transition-all ${viewMode === 'list' ? 'bg-white shadow-sm text-brand-600' : 'text-slate-400 hover:text-slate-600'}`}
                          title="Vue en liste"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                        </button>
                      </div>
                    )}
                    <div className="relative">
                      <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                      <input
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        placeholder="Rechercher..."
                        className="pl-7 pr-3 py-1.5 text-sm border border-slate-200 rounded-lg text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition"
                      />
                    </div>
                  </div>
                </div>

                {/* Liste entreprises (pré-génération) */}
                {!isGenerationView && viewMode === 'grid' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 px-8 py-6 bg-slate-50/50">
                    {hasHiringSplit && (
                      <div className="col-span-full text-sm font-semibold text-slate-700 pt-1 pb-2 border-b border-slate-200">
                        Ces entreprises seraient à la recherche d&apos;un {campaign?.jobTitle}
                      </div>
                    )}
                    {sortedFilteredCompanies.map((company, idx) => (
                      <Fragment key={company.id}>
                        {hasHiringSplit && idx === filteredHiringCompanies.length && (
                          <div className="col-span-full text-sm font-semibold text-slate-700 pt-3 pb-2 border-b border-slate-200">
                            Ces entreprises seraient potentiellement intéressées par vous
                          </div>
                        )}
                      <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-sm hover:shadow-md hover:border-brand-300 transition-all group flex flex-col justify-between gap-4 relative overflow-hidden">

                        {/* Status bar */}
                        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand-300 to-brand-500 opacity-0 group-hover:opacity-100 transition-opacity" />

                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <h3 className="text-[15px] font-bold text-slate-900 leading-tight pr-6">{company.name}</h3>
                            <button
                              onClick={() => handleDeleteCompany(company.id)}
                              disabled={deletingId === company.id}
                              className="w-7 h-7 absolute top-3 right-3 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all hover:bg-red-500 hover:text-white shrink-0 disabled:opacity-50 z-10"
                              title="Supprimer"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                          </div>

                          <div className="flex flex-wrap gap-2 mb-4">
                            {company.source === 'datagouv' && <span className="text-[10px] uppercase tracking-wider font-bold bg-sky-50 text-sky-600 border border-sky-100 px-2 py-0.5 rounded-md">Data.gouv</span>}
                            {company.status === 'enriched' && <span className="text-[10px] uppercase tracking-wider font-bold bg-violet-50 text-violet-600 border border-violet-100 px-2 py-0.5 rounded-md">Enrichie</span>}
                          </div>

                          <div className="space-y-2.5">
                            {company.address && (
                              <div className="flex items-start gap-2 text-xs text-slate-500 group-hover:text-slate-700 transition-colors">
                                <svg className="w-4 h-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                <span className="line-clamp-2 leading-relaxed">{company.address}</span>
                              </div>
                            )}
                            {company.phone && (
                              <div className="flex items-center gap-2 text-xs text-slate-500 group-hover:text-slate-700 transition-colors">
                                <svg className="w-4 h-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                <span>{company.phone}</span>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Footer card */}
                        <div className="pt-4 mt-auto border-t border-slate-100 flex items-center justify-between gap-3 relative z-10 bg-white">
                          <div className="flex flex-wrap gap-1">
                            {(company.enriched?.resultats ?? []).some(r => r.mail) && (
                              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200/50 px-2.5 py-1 rounded-md">
                                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                {(company.enriched?.resultats ?? []).filter(r => r.mail).length} contact{(company.enriched?.resultats ?? []).filter(r => r.mail).length > 1 ? 's' : ''}
                              </span>
                            )}
                          </div>

                          {company.website && (
                            <a href={company.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-50 hover:bg-brand-50 border border-slate-200 hover:border-brand-200 text-slate-500 hover:text-brand-600 transition-colors shrink-0" title="Visiter le site web">
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                            </a>
                          )}
                        </div>
                      </div>
                      </Fragment>
                    ))}
                  </div>
                )}

                {!isGenerationView && viewMode === 'list' && (
                  <div className="flex flex-col">
                    {hasHiringSplit && (
                      <div className="px-8 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50 border-b border-slate-200">
                        Ces entreprises seraient à la recherche d&apos;un {campaign?.jobTitle}
                      </div>
                    )}
                    {sortedFilteredCompanies.map((company, idx) => (
                      <Fragment key={company.id}>
                        {hasHiringSplit && idx === filteredHiringCompanies.length && (
                          <div className="px-8 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50 border-b border-slate-200">
                            Ces entreprises seraient potentiellement intéressées par vous
                          </div>
                        )}
                      <div className="px-8 py-3.5 border-b border-slate-50 hover:bg-slate-50/50 transition-colors group flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-sm font-medium text-slate-900">{company.name}</p>
                            {company.source === 'datagouv' && <span className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-medium">data.gouv</span>}
                            {company.status === 'enriched' && <span className="text-xs bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded font-medium">Enrichie</span>}
                          </div>
                          <div className="flex flex-wrap gap-x-3 mt-0.5">
                            {company.address && <span className="text-xs text-slate-400">{company.address}</span>}
                            {company.phone && <span className="text-xs text-slate-400">{company.phone}</span>}
                          </div>
                          {(company.enriched?.resultats ?? []).some(r => r.mail) && (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              {(company.enriched?.resultats ?? []).filter(r => r.mail).map(r => (
                                <span key={r.mail!} className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-mono">{r.mail}</span>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {company.website && (
                            <a href={company.website} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-500 hover:underline">Site →</a>
                          )}
                          <button
                            onClick={() => handleDeleteCompany(company.id)}
                            disabled={deletingId === company.id}
                            className="w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 disabled:opacity-50"
                          >
                            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
                          </button>
                        </div>
                      </div>
                      </Fragment>
                    ))}
                  </div>
                )}

                {/* Liste entreprises (post-génération compact) */}
                {isGenerationView && blocks.map(b => (
                  <div key={b.companyId} className="px-8 py-3.5 border-b border-slate-50 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 truncate">{b.companyName}</p>
                      {b.companyAddress && <p className="text-xs text-slate-400 truncate">{b.companyAddress}</p>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-slate-400">{b.emails.length} mail{b.emails.length !== 1 ? 's' : ''}</span>
                      <span className="text-xs bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded font-medium">Enrichie</span>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* EN COURS */}
        {activeTab === 'en_cours' && (
          <div className="px-8 py-6 space-y-3">
            {generating && (
              <p className="text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-4 py-3 text-center">
                L&apos;enrichissement et la rédaction peuvent prendre <strong className="text-slate-700">quelques minutes</strong> selon le nombre d&apos;entreprises.
              </p>
            )}
            {Array.from(processingMap.values()).map(p => (
              <div key={p.companyId} className="border border-slate-200 rounded-xl px-5 py-4 flex items-center gap-4">
                <span className="w-4 h-4 border-2 border-brand-400 border-t-transparent rounded-full animate-spin shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900">{p.companyName}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {p.state === 'enriching' ? 'Recherche des contacts en ligne...' : 'Rédaction du mail personnalisé...'}
                  </p>
                </div>
                <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-medium shrink-0">
                  {p.state === 'enriching' ? 'Enrichissement' : 'Rédaction'}
                </span>
              </div>
            ))}
            {queuedCompanies.map(c => (
              <div key={c.id} className="border border-slate-100 rounded-xl px-5 py-3.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm text-slate-500 truncate">{c.name}</p>
                  {c.address && <p className="text-xs text-slate-400 truncate">{c.address}</p>}
                </div>
                <span className="text-xs text-slate-400">En attente</span>
              </div>
            ))}
            {!generating && processingMap.size === 0 && queuedCompanies.length === 0 && (
              <div className="py-16 text-center">
                <p className="text-sm font-medium text-slate-600">Traitement terminé</p>
                <p className="text-xs text-slate-400 mt-1">{draftEmails.length} mail{draftEmails.length !== 1 ? 's' : ''} prêt{draftEmails.length !== 1 ? 's' : ''} à envoyer</p>
                <button onClick={() => setActiveTab('en_attente')} className="mt-4 text-sm text-brand-500 hover:underline font-medium">Voir les mails →</button>
              </div>
            )}
          </div>
        )}

        {/* EN ATTENTE */}
        {activeTab === 'en_attente' && (
          <>
            {/* Vue fiche entreprise */}
            {selectedCompanyId ? (() => {
              const block = blocks.find(b => b.companyId === selectedCompanyId)
              if (!block) return null
              return (
                <CompanyDetailView
                  block={block}
                  campaignName={campaign.name}
                  onBack={() => setSelectedCompanyId(null)}
                  sending={sending}
                  onSend={sendEmail}
                />
              )
            })() : (
              /* Vue liste entreprises */
              <div className="px-8 py-6">
                {draftEmails.length === 0 ? (
                  <div className="py-16 text-center">
                    <p className="text-xs text-slate-400">
                      {generating ? "Les mails apparaîtront ici dès qu'ils sont générés" : 'Aucun mail en attente'}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {blocks.filter(b => b.emails.some(e => e.status === 'draft')).map(block => {
                      const count = block.emails.filter(e => e.status === 'draft').length
                      return (
                        <button
                          key={block.companyId}
                          onClick={() => setSelectedCompanyId(block.companyId)}
                          className="w-full text-left border border-slate-100 hover:border-brand-200 rounded-xl px-5 py-4 flex items-center justify-between gap-3 transition-all hover:shadow-sm group bg-white"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-slate-900 group-hover:text-brand-600 transition-colors truncate">
                              {block.companyName}
                            </p>
                            {block.companyAddress && (
                              <p className="text-xs text-slate-400 truncate mt-0.5">{block.companyAddress}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2.5 shrink-0">
                            {block.enriched?.resultats?.some(r => r.mail) && (
                              <span className="text-xs bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded font-medium">
                                Enrichie
                              </span>
                            )}
                            <span className="text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-medium">
                              {count} mail{count !== 1 ? 's' : ''}
                            </span>
                            <svg className="w-3.5 h-3.5 text-slate-300 group-hover:text-brand-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ENVOYÉS */}
        {activeTab === 'envoyes' && (
          <div className="px-8 py-6 space-y-2">
            {sentEmails.length === 0 ? (
              <div className="py-16 text-center">
                <p className="text-xs text-slate-400">Aucun mail envoyé pour l&apos;instant</p>
              </div>
            ) : sentEmails.map(email => (
              <div key={email.id} className="border border-slate-100 rounded-xl px-5 py-4 flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900 truncate">{email.companyName}</p>
                  <p className="text-xs text-slate-400 mt-0.5 truncate">
                    {email.recipientName ?? email.to ?? 'Destinataire inconnu'}
                    {email.to && <span className="font-mono ml-2">{email.to}</span>}
                  </p>
                  <p className="text-xs text-slate-400 truncate mt-0.5">{email.subject}</p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className="text-xs bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-medium">Envoyé</span>
                  {email.sentAt && (
                    <span className="text-xs text-slate-400">
                      {new Date(email.sentAt).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

      </div>

      {launchModalOpen && (
        <LaunchModal
          campaignId={id}
          totalDraft={draftEmails.length}
          onClose={() => setLaunchModalOpen(false)}
          onSuccess={handleLaunchSuccess}
        />
      )}

      <SelectCompaniesModal
        open={selectCompaniesOpen}
        totalCompanies={companies.length}
        onConfirm={() => {
          setSelectCompaniesOpen(false)
          setPreGenerateOpen(true)
        }}
        onCancel={() => setSelectCompaniesOpen(false)}
      />

      <PreGenerateModal
        open={preGenerateOpen}
        onConfirm={handleGenerate}
        onCancel={() => setPreGenerateOpen(false)}
      />
    </div>
  )
}
