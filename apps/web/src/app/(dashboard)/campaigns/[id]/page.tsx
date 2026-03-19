'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import PipelineStepper from './PipelineStepper'
import ActivityLog, { type ActivityEvent } from './ActivityLog'
import PaywallModal from './PaywallModal'
import LaunchModal from './LaunchModal'
import CompanyDetailView from './CompanyDetailView'
import PreGenerateModal, { type PreGenerateOptions } from './PreGenerateModal'

// ── Types ────────────────────────────────────────────────────────────

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

type EnrichedData = { resultats: EnrichedContact[] }

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
  score?: number | null
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
type PipelineStep = 1 | 2 | 3 | 4
type StepStatus = 'pending' | 'active' | 'completed'

// ── Helpers ──────────────────────────────────────────────────────────

function logId() {
  return Math.random().toString(36).slice(2, 10)
}

function fmtHour(h: number | null) {
  if (h === null) return ''
  return `${String(h).padStart(2, '0')}h`
}

// ── Main Page ────────────────────────────────────────────────────────

export default function CampaignPage({ params }: { params: { id: string } }) {
  const { id } = params
  const router = useRouter()

  // ── Core data ───────────────────────────────────
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [blocks, setBlocks] = useState<GeneratedBlock[]>([])
  const [processingMap, setProcessingMap] = useState<Map<string, CompanyProcessing>>(new Map())
  const [enrichedCompanies, setEnrichedCompanies] = useState<Map<string, { companyId: string; companyName: string; enriched: EnrichedData }>>(new Map())

  // ── Pipeline state ──────────────────────────────
  const [pipelineStep, setPipelineStep] = useState<PipelineStep>(1)
  const [stepStatuses, setStepStatuses] = useState<Record<PipelineStep, StepStatus>>({
    1: 'pending', 2: 'pending', 3: 'pending', 4: 'pending',
  })

  // ── UI state ────────────────────────────────────
  const [scraping, setScraping] = useState(false)
  const [scrapePhase, setScrapePhase] = useState<'recherche' | 'filtrage'>('recherche')
  const [generating, setGenerating] = useState(false)
  const [message, setMessage] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [sending, setSending] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [hoveringStop, setHoveringStop] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [launchPending, setLaunchPending] = useState(false)
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null)
  const [expandedCompanyId, setExpandedCompanyId] = useState<string | null>(null)

  // ── Modals ──────────────────────────────────────
  const [paywallOpen, setPaywallOpen] = useState(false)
  const [paywallCount, setPaywallCount] = useState(0)
  const [preGenerateOpen, setPreGenerateOpen] = useState(false)
  const [launchModalOpen, setLaunchModalOpen] = useState(false)

  // ── Activity log ────────────────────────────────
  const [activityLog, setActivityLog] = useState<ActivityEvent[]>([])

  // ── Sub-phases "Identification décideurs" ────────
  type SubPhaseState = 'idle' | 'running' | 'done'
  const [apolloPhase, setApolloPhase] = useState<{ state: SubPhaseState; total: number; filled: number }>({ state: 'idle', total: 0, filled: 0 })
  const [neverBouncePhase, setNeverBouncePhase] = useState<{ state: SubPhaseState; total: number; valid: number; removed: number }>({ state: 'idle', total: 0, valid: 0, removed: 0 })

  // ── Refs ─────────────────────────────────────────
  const eventSourceRef = useRef<EventSource | null>(null)
  const connectToJobRef = useRef<(jobId: string) => void>(() => {})
  const hasAutoScraped = useRef(false)

  // ── Derived data ────────────────────────────────
  const allEmails: FlatEmail[] = blocks.flatMap(b => b.emails.map(e => ({ ...e, companyName: b.companyName })))
  const draftEmails = allEmails.filter(e => e.status === 'draft')
  const sentEmails = allEmails.filter(e => e.status === 'sent').sort((a, b) => (b.sentAt ?? '').localeCompare(a.sentAt ?? ''))
  const isLaunched = campaign?.status === 'active' || campaign?.status === 'paused' || campaign?.status === 'finished'
  const filteredCompanies = companies
    .filter(c =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.address ?? '').toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const aIsJT = a.source === 'apollo_jobtitle'
      const bIsJT = b.source === 'apollo_jobtitle'
      if (aIsJT && !bIsJT) return -1
      if (!aIsJT && bIsJT) return 1
      return (b.score ?? 0) - (a.score ?? 0)
    })
  const filteredHiringCompanies = filteredCompanies.filter(c => c.source === 'apollo_jobtitle')
  const filteredPotentialCompanies = filteredCompanies.filter(c => c.source !== 'apollo_jobtitle')
  const totalDecideurs = companies.reduce((acc, c) => acc + (c.enriched?.resultats?.filter(r => r.mail).length ?? 0), 0)

  // ── Log helper ──────────────────────────────────
  const addLog = useCallback((type: ActivityEvent['type'], message: string, detail?: string) => {
    setActivityLog(prev => [...prev, { id: logId(), timestamp: new Date(), type, message, detail }])
  }, [])

  // ── Step helpers ────────────────────────────────
  function setStep(step: PipelineStep, status: StepStatus) {
    setStepStatuses(prev => ({ ...prev, [step]: status }))
  }

  function advanceTo(step: PipelineStep) {
    setPipelineStep(step)
    setStepStatuses(prev => {
      const next = { ...prev }
      // Mark all previous steps completed
      for (let i = 1 as PipelineStep; i < step; i++) {
        next[i as PipelineStep] = 'completed'
      }
      next[step] = 'active'
      return next
    })
  }

  // ── Load emails helper ──────────────────────────
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
        id: email.id, subject: email.subject, body: email.body,
        to: email.to ?? null, recipientName: email.recipientName ?? null,
        generatedLm: email.generatedLm ?? null, status: email.status, sentAt: email.sentAt ?? null,
      })
    }
    setBlocks(Array.from(map.values()))
  }, [])

  const refreshEmails = useCallback(() => {
    fetch(`/api/campaigns/${id}/emails`).then(r => r.json()).then(loadEmails)
    fetch(`/api/campaigns/${id}`).then(r => r.json()).then(setCampaign)
  }, [id, loadEmails])

  // ── SSE connection ──────────────────────────────
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
          addLog('progress', `Enrichissement de ${event.companyName}...`)
        } else if (event.type === 'enriched') {
          // Phase 1 terminée pour cette entreprise → move processingMap → enrichedCompanies
          setProcessingMap(prev => { const next = new Map(prev); next.delete(event.companyId); return next })
          setEnrichedCompanies(prev => new Map(prev).set(event.companyId, {
            companyId: event.companyId,
            companyName: event.companyName,
            enriched: event.enriched ?? { resultats: [] },
          }))
          addLog('success', `${event.companyName} enrichi`)
        } else if (event.type === 'apollo_fill_start') {
          setApolloPhase({ state: 'running', total: event.total, filled: 0 })
          addLog('progress', `Enrichissement supplémentaire : recherche pour ${event.total} contact(s)...`)
        } else if (event.type === 'apollo_fill_done') {
          setApolloPhase({ state: 'done', total: event.total, filled: event.filled })
          addLog('success', `Enrichissement supplémentaire : ${event.filled}/${event.total} email(s) récupéré(s)`)
        } else if (event.type === 'verifying_emails') {
          setNeverBouncePhase({ state: 'running', total: event.total, valid: 0, removed: 0 })
          addLog('progress', `Vérification des emails : ${event.total} adresse(s) en cours...`)
        } else if (event.type === 'emails_verified') {
          setNeverBouncePhase({ state: 'done', total: event.total, valid: event.valid, removed: event.removed })
          addLog('success', `Vérification : ${event.valid} email(s) valide(s)${event.removed > 0 ? `, ${event.removed} supprimé(s)` : ''}`)
        } else if (event.type === 'generating') {
          // Phase 2 démarre pour cette entreprise → move enrichedCompanies → processingMap
          setEnrichedCompanies(prev => { const next = new Map(prev); next.delete(event.companyId); return next })
          setProcessingMap(prev => new Map(prev).set(event.companyId, { companyId: event.companyId, companyName: event.companyName, state: 'generating' }))
          addLog('progress', `Rédaction pour ${event.companyName}...`)
          // Advance to step 3 (à la première entreprise en phase 2)
          setPipelineStep(3)
          setStepStatuses(prev => ({ ...prev, 2: 'completed', 3: 'active' }))
        } else if (event.type === 'done') {
          setBlocks(prev => [...prev, event as GeneratedBlock])
          setProcessingMap(prev => { const next = new Map(prev); next.delete(event.companyId); return next })
          const emailCount = (event as GeneratedBlock).emails?.length ?? 0
          addLog('success', `${event.companyName} traité`, `${emailCount} email${emailCount > 1 ? 's' : ''} généré${emailCount > 1 ? 's' : ''}`)
        } else if (event.type === 'complete') {
          setGenerating(false)
          setProcessingMap(new Map())
          setEnrichedCompanies(new Map())
          setLaunchPending(false)
          setMessage('')
          es.close()
          eventSourceRef.current = null
          addLog('success', 'Pipeline terminé !')
          advanceTo(4)
          fetch(`/api/campaigns/${id}`).then(r => r.json()).then(setCampaign)
          fetch(`/api/campaigns/${id}/emails`).then(r => r.json()).then(loadEmails)
        } else if (event.type === 'error') {
          setMessage(event.message ?? 'Erreur')
          setGenerating(false)
          addLog('error', event.message ?? 'Erreur lors du traitement')
          es.close()
          eventSourceRef.current = null
        }
      } catch { /* SSE malformée */ }
    }
  }

  // ── Cleanup SSE ──────────────────────────────────
  useEffect(() => {
    return () => { eventSourceRef.current?.close() }
  }, [])

  // ── Initial data load ───────────────────────────
  useEffect(() => {
    fetch(`/api/campaigns/${id}`).then(r => r.json()).then((data: Campaign) => {
      setCampaign(data)
      // Determine initial pipeline step from campaign status
      if (data.status === 'scraped') {
        advanceTo(1)
        setStep(1, 'completed')
      } else if (data.status === 'generating') {
        advanceTo(2)
      } else if (data.status === 'emails_generated') {
        setPipelineStep(4)
        setStepStatuses({ 1: 'completed', 2: 'completed', 3: 'completed', 4: 'active' })
        addLog('success', 'Mails générés — prêts à être envoyés')
      } else if (data.status === 'active' || data.status === 'paused' || data.status === 'finished') {
        setPipelineStep(4)
        setStepStatuses({ 1: 'completed', 2: 'completed', 3: 'completed', 4: 'completed' })
        const sentCount = data.sentCount ?? 0
        const statusLabel = data.status === 'active' ? 'active' : data.status === 'paused' ? 'en pause' : 'terminée'
        addLog('info', `Campagne ${statusLabel}`, `${sentCount} mail${sentCount > 1 ? 's' : ''} envoyé${sentCount > 1 ? 's' : ''}`)
      }
    })
    fetch(`/api/campaigns/${id}/companies`).then(r => r.json()).then(data => {
      setCompanies(Array.isArray(data) ? data : [])
    })
    fetch(`/api/campaigns/${id}/emails`).then(r => r.json()).then(loadEmails)
  }, [id, loadEmails])

  // ── Auto-scrape on draft ────────────────────────
  useEffect(() => {
    if (campaign?.status === 'draft' && !hasAutoScraped.current) {
      hasAutoScraped.current = true
      // Don't auto-scrape — wait for user to click "Lancer le pipeline"
    }
  }, [campaign])

  // ── Auto-reconnect to running job ───────────────
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
          advanceTo(2)
          addLog('info', 'Reconnexion au pipeline en cours...')
          connectToJobRef.current(data.jobId)
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaign?.status])

  // ── Polling when active ─────────────────────────
  useEffect(() => {
    if (campaign?.status !== 'active') return
    const interval = setInterval(refreshEmails, 30000)
    return () => clearInterval(interval)
  }, [campaign?.status, refreshEmails])

  // ── Actions ─────────────────────────────────────

  async function handleScrape() {
    setScraping(true)
    setScrapePhase('recherche')
    setMessage('')
    setCompanies([])
    setStep(1, 'active')
    setPipelineStep(1)
    addLog('info', 'Lancement du scraping...')
    addLog('progress', 'Recherche des entreprises en cours...')

    try {
      const res = await fetch(`/api/campaigns/${id}/scrape`, { method: 'POST' })
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({ error: 'Erreur service' }))
        setMessage(data.error ?? 'Erreur lors de la recherche')
        addLog('error', data.error ?? 'Erreur lors du scraping')
        setScraping(false)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let filterStarted = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          try {
            const event = JSON.parse(jsonStr)

            if (event.type === 'ranking') {
              setScrapePhase('filtrage')
              addLog('progress', `Filtrage IA de ${event.count} entreprises...`)
            } else if (event.type === 'company' && event.company) {
              if (!filterStarted) {
                filterStarted = true
                setScrapePhase('filtrage')
              }
              setCompanies(prev => [...prev, { ...event.company, score: event.score ?? null }])
            } else if (event.type === 'done') {
              setStep(1, 'completed')
              addLog('success', `${event.total} entreprise${event.total > 1 ? 's' : ''} trouvée${event.total > 1 ? 's' : ''}`)
            } else if (event.type === 'error') {
              addLog('error', event.error ?? 'Erreur lors du scraping')
            }
          } catch { /* ignorer events mal formés */ }
        }
      }
    } catch (err) {
      setMessage('Erreur lors de la recherche')
      addLog('error', 'Erreur lors du scraping')
    }
    setScraping(false)
  }

  async function handleGenerate(opts: PreGenerateOptions) {
    setPreGenerateOpen(false)
    setGenerating(true)
    setBlocks([])
    setEnrichedCompanies(new Map())
    setMessage('')
    setProcessingMap(new Map())
    setApolloPhase({ state: 'idle', total: 0, filled: 0 })
    setNeverBouncePhase({ state: 'idle', total: 0, valid: 0, removed: 0 })
    advanceTo(2)
    addLog('info', 'Démarrage de l\'enrichissement et de la rédaction...')

    if (opts.extraFiles.length > 0) {
      const formData = new FormData()
      for (const f of opts.extraFiles) formData.append('files', f)
      await fetch(`/api/campaigns/${id}/attachments`, { method: 'POST', body: formData })
    }

    const res = await fetch(`/api/campaigns/${id}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        links: opts.links,
        userMailTemplate: opts.userMailTemplate || null,
        userMailSubject: opts.userMailSubject || null,
        poolLimit: opts.poolLimit || null,
        autoStart: opts.autoStart,
        dailyLimit: opts.autoStart ? opts.dailyLimit : null,
        sendStartHour: opts.autoStart ? opts.sendStartHour : null,
        sendEndHour: opts.autoStart ? opts.sendEndHour : null,
      }),
    })
    if (!res.ok) {
      setMessage('Erreur lors du lancement de la génération')
      setGenerating(false)
      addLog('error', 'Erreur lors du lancement')
      return
    }

    const { jobId } = await res.json()
    if (!jobId) {
      setMessage('Erreur : aucun job ID reçu')
      setGenerating(false)
      addLog('error', 'Aucun job ID reçu')
      return
    }

    connectToJobRef.current(jobId)
  }

  async function sendEmail(emailId: string) {
    setSending(emailId)
    const emailMeta = allEmails.find(e => e.id === emailId)
    const res = await fetch(`/api/emails/${emailId}/send`, { method: 'POST' })
    const data = await res.json()
    if (res.ok) {
      setBlocks(prev => prev.map(b => ({
        ...b,
        emails: b.emails.map(e => e.id === emailId ? { ...e, status: 'sent' } : e),
      })))
      addLog('success', `Mail envoyé — ${emailMeta?.companyName ?? ''}`, emailMeta?.to ?? undefined)
    } else {
      setMessage(data.error ?? "Erreur d'envoi")
      addLog('error', `Échec d'envoi — ${emailMeta?.companyName ?? ''}`, data.error ?? "Erreur inconnue")
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
    if (res.ok) router.push('/dashboard')
    else setDeleting(false)
  }

  async function handleDeleteCompany(companyId: string) {
    setDeletingId(companyId)
    const res = await fetch(`/api/campaigns/${id}/companies/${companyId}`, { method: 'DELETE' })
    if (res.ok) setCompanies(prev => prev.filter(c => c.id !== companyId))
    setDeletingId(null)
  }

  function handleLaunchSuccess(pending?: boolean) {
    setLaunchModalOpen(false)
    if (pending) {
      setLaunchPending(true)
      addLog('info', 'Lancement automatique programmé')
    } else {
      fetch(`/api/campaigns/${id}`).then(r => r.json()).then(setCampaign)
      addLog('success', 'Campagne lancée !')
    }
  }

  function nextSendLabel(): string {
    if (!campaign?.dailyLimit) return ''
    const intervalMin = Math.floor(1440 / campaign.dailyLimit)
    const lastSentEmail = sentEmails[0]
    if (!lastSentEmail?.sentAt) return 'dans les prochaines minutes'
    const elapsed = (Date.now() - new Date(lastSentEmail.sentAt).getTime()) / 60000
    const remaining = Math.max(0, Math.ceil(intervalMin - elapsed))
    return remaining <= 1 ? 'imminent' : `dans ~${remaining} min`
  }

  // ── Loading ─────────────────────────────────────
  if (!campaign) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <span className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-slate-600">Chargement...</p>
        </div>
      </div>
    )
  }

  // ── Render ──────────────────────────────────────
  return (
    <div className="flex flex-col h-full bg-slate-50">
     <div className="flex flex-col h-full max-w-[80%] mx-auto w-full">

      {/* ── Header ─────────────────────────────── */}
      <div className="px-6 py-4 bg-white border-b border-slate-300 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-lg font-bold text-slate-900">{campaign.name}</h1>
          <p className="text-sm text-slate-600 mt-0.5">{campaign.jobTitle} · {campaign.location}</p>
        </div>
        <div className="flex items-center gap-2">
          {campaign.status === 'active' && (
            <button
              onMouseEnter={() => setHoveringStop(true)}
              onMouseLeave={() => setHoveringStop(false)}
              onClick={handleStop}
              className={`inline-flex items-center gap-1.5 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all ${
                hoveringStop ? 'bg-red-500 hover:bg-red-600' : 'bg-emerald-500 hover:bg-emerald-600'
              }`}
            >
              {hoveringStop ? 'Stopper' : '● Active'}
            </button>
          )}
          {campaign.status === 'paused' && (
            <>
              <button onClick={handleDelete} disabled={deleting} className="inline-flex items-center gap-1.5 border border-red-200 text-red-500 hover:bg-red-50 disabled:opacity-40 text-sm font-medium px-3 py-2 rounded-lg transition-colors">
                Supprimer
              </button>
              <button onClick={() => setLaunchModalOpen(true)} className="inline-flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors">
                Reprendre
              </button>
            </>
          )}
          {campaign.status === 'finished' && (
            <button onClick={handleDelete} disabled={deleting} className="inline-flex items-center gap-1.5 border border-red-200 text-red-500 hover:bg-red-50 disabled:opacity-40 text-sm font-medium px-3 py-2 rounded-lg transition-colors">
              Supprimer
            </button>
          )}
        </div>
      </div>

      {/* ── Pipeline stepper ───────────────────── */}
      <div className="px-6 pt-5">
        <PipelineStepper stepStatuses={stepStatuses} campaignStatus={campaign.status} />
      </div>

      {/* ── Two-column layout ──────────────────── */}
      <div className="flex-1 flex gap-5 px-6 py-5 overflow-hidden min-h-0">

        {/* ── Left: main content ─────────────── */}
        <div className="flex-1 bg-white border border-slate-300 rounded-2xl overflow-y-auto">

          {/* ── STEP 1: Scraping ─────────────── */}
          {pipelineStep === 1 && (
            <div>
              {/* Not started yet */}
              {!scraping && companies.length === 0 && stepStatuses[1] !== 'completed' && (
                <div className="p-8 flex flex-col items-center justify-center py-16 text-center">
                  <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
                    <svg className="w-7 h-7 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                  </div>
                  <p className="text-sm text-slate-600 mb-6">
                    Lancez le pipeline pour rechercher des entreprises et générer vos candidatures.
                  </p>
                  <button
                    onClick={handleScrape}
                    className="inline-flex items-center gap-2.5 bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold px-6 py-2.5 rounded-lg transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Lancer le pipeline
                  </button>
                </div>
              )}

              {/* Scraping in progress */}
              {scraping && (
                <div className="p-8 flex flex-col items-center justify-center py-16">
                  <span className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin mb-4" />
                  <p className="text-sm text-slate-600 font-medium">
                    {scrapePhase === 'filtrage' ? 'Filtrage des entreprises...' : 'Recherche des entreprises...'}
                  </p>
                  <p className="text-xs text-slate-600 mt-1.5">Cela peut prendre quelques minutes</p>
                </div>
              )}

              {/* Companies found */}
              {!scraping && companies.length > 0 && (
                <div>
                  {/* Header: title + search + Suivant */}
                  <div className="px-6 py-4 flex items-center justify-between border-b border-slate-200">
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-bold text-slate-900">Résultats du scraping</h3>
                      <span className="text-xs text-slate-500 font-medium">{filteredCompanies.length} résultats</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        <input
                          value={search}
                          onChange={e => setSearch(e.target.value)}
                          placeholder="Rechercher..."
                          className="pl-7 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition w-40"
                        />
                      </div>
                      <button
                        onClick={() => setPaywallOpen(true)}
                        className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors"
                      >
                        Suivant
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                      </button>
                    </div>
                  </div>

                  {/* Company rows — directly in the panel */}
                  <div className="divide-y divide-slate-200 max-h-[520px] overflow-y-auto">
                    {filteredCompanies.map(company => {
                        const isExpanded = expandedCompanyId === company.id
                        const initial = company.name.charAt(0).toUpperCase()
                        const contacts = company.enriched?.resultats?.filter(r => r.mail) ?? []
                        const sector = company.source === 'apollo_jobtitle' ? campaign.jobTitle : (company.siren ? 'Entreprise' : 'Entreprise')
                        const city = company.address?.split(',').pop()?.trim() ?? ''

                        return (
                          <div key={company.id}>
                            <button
                              onClick={() => setExpandedCompanyId(isExpanded ? null : company.id)}
                              className="w-full text-left px-5 py-3.5 flex items-center gap-4 hover:bg-slate-50/80 transition-colors group"
                            >
                              {/* Avatar */}
                              <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center shrink-0">
                                <span className="text-sm font-bold text-slate-600">{initial}</span>
                              </div>

                              {/* Name + sector */}
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold text-slate-900 truncate">{company.name}</p>
                                <p className="text-xs text-slate-600 truncate">
                                  {sector}{city ? ` · ${city}` : ''}
                                </p>
                              </div>

                              {/* Right side */}
                              <div className="flex items-center gap-3 shrink-0">
                                {contacts.length > 0 && (
                                  <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                  </span>
                                )}
                                <svg className={`w-4 h-4 text-slate-600 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </div>
                            </button>

                            {/* Expanded details */}
                            {isExpanded && (
                              <div className="px-5 pb-4 pt-1 ml-14 mr-5 space-y-3">
                                {company.address && (
                                  <div className="flex items-start gap-2">
                                    <svg className="w-3.5 h-3.5 text-slate-600 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                    <span className="text-xs text-slate-600">{company.address}</span>
                                  </div>
                                )}
                                {company.phone && (
                                  <div className="flex items-center gap-2">
                                    <svg className="w-3.5 h-3.5 text-slate-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                    <span className="text-xs text-slate-600">{company.phone}</span>
                                  </div>
                                )}
                                {contacts.length > 0 && (
                                  <div>
                                    <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-1.5">Contacts trouvés</p>
                                    <div className="space-y-1">
                                      {contacts.map((r, i) => (
                                        <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                                          <span className="font-medium">{r.prenom} {r.nom}</span>
                                          {r.role && <span className="text-slate-600">· {r.role}</span>}
                                          {r.mail && <span className="font-mono text-slate-600">{r.mail}</span>}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                <div className="flex items-center gap-2 pt-1">
                                  {company.website && (
                                    <a
                                      href={company.website}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700 bg-brand-50 hover:bg-brand-100 border border-brand-200 px-3 py-1.5 rounded-lg transition-colors"
                                    >
                                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                                      Voir le site
                                    </a>
                                  )}
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleDeleteCompany(company.id) }}
                                    disabled={deletingId === company.id}
                                    className="inline-flex items-center gap-1.5 text-xs font-medium text-red-500 hover:text-red-600 hover:bg-red-50 border border-red-200 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                                  >
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
                                    Retirer
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>

                  {filteredCompanies.length === 0 && (
                    <p className="text-sm text-slate-600 text-center py-8">Aucune entreprise ne correspond à votre recherche.</p>
                  )}
                </div>
              )}

              {/* Scrape done, no results */}
              {!scraping && companies.length === 0 && stepStatuses[1] === 'completed' && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <p className="text-sm text-slate-600 mb-4">Aucune entreprise trouvée.</p>
                  <button onClick={handleScrape} className="text-sm text-brand-600 hover:underline font-medium">
                    Relancer la recherche
                  </button>
                </div>
              )}

              {message && (
                <div className="mx-6 mb-4 mt-2 p-3 bg-red-50 border border-red-100 rounded-lg">
                  <p className="text-sm text-red-600 font-medium">{message}</p>
                </div>
              )}
            </div>
          )}

          {/* ── STEP 2: Enrichment ───────────── */}
          {pipelineStep === 2 && (() => {
            const enrichedIds = new Set(enrichedCompanies.keys())
            const processingIds = new Set(processingMap.keys())
            const sortedPool = [...companies]
              .sort((a, b) => {
                if (a.source === 'apollo_jobtitle' && b.source !== 'apollo_jobtitle') return -1
                if (b.source === 'apollo_jobtitle' && a.source !== 'apollo_jobtitle') return 1
                return 0
              })
              .slice(0, paywallCount > 0 ? paywallCount : companies.length)
            const waitingCompanies = sortedPool.filter(c => !enrichedIds.has(c.id) && !processingIds.has(c.id))

            // Métriques — depuis les données enrichies disponibles (phase 1)
            const decideurs = Array.from(enrichedCompanies.values())
              .flatMap(e => e.enriched?.resultats ?? [])
              .filter(r => r.type === 'specialise' && r.mail).length

            return (
              <div className="p-8 space-y-4">
                {/* Métriques */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-slate-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-slate-900 tabular-nums">{decideurs}</p>
                    <p className="text-xs text-slate-500 mt-1">Décideurs trouvés</p>
                  </div>
                  <div className="border border-slate-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-slate-900 tabular-nums">{enrichedCompanies.size}</p>
                    <p className="text-xs text-slate-500 mt-1">Entreprises enrichies</p>
                  </div>
                </div>

                {generating && (
                  <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-4 flex gap-3 items-start">
                    <svg className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-xs text-blue-700 leading-relaxed">
                      L&apos;enrichissement peut prendre du temps <strong>(plusieurs heures</strong> en fonction du nombre d&apos;entreprises).
                      Vous pouvez partir — nous vous enverrons un mail une fois l&apos;enrichissement terminé !
                    </p>
                  </div>
                )}

                {/* Enrichies (phase 1 terminée) */}
                {Array.from(enrichedCompanies.values()).map(e => {
                  const resultats = e.enriched?.resultats ?? []
                  const nbDecideurs = resultats.filter(r => r.type === 'specialise' && r.mail).length
                  const nbGeneriques = resultats.filter(r => r.type === 'generique' && r.mail).length
                  const nbTotal = nbDecideurs + nbGeneriques

                  let contactLabel: string
                  let contactColor: string
                  if (nbDecideurs > 0) {
                    contactLabel = `${nbDecideurs} décideur${nbDecideurs > 1 ? 's' : ''}${nbGeneriques > 0 ? ` + ${nbGeneriques} générique${nbGeneriques > 1 ? 's' : ''}` : ''}`
                    contactColor = 'text-emerald-600'
                  } else if (nbGeneriques > 0) {
                    contactLabel = `${nbGeneriques} contact${nbGeneriques > 1 ? 's' : ''} générique${nbGeneriques > 1 ? 's' : ''}`
                    contactColor = 'text-slate-500'
                  } else {
                    contactLabel = 'Aucun contact trouvé'
                    contactColor = 'text-slate-400'
                  }

                  return (
                    <div key={e.companyId} className="border border-emerald-100 bg-emerald-50/50 rounded-xl px-5 py-3.5 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        <p className="text-sm font-medium text-slate-800">{e.companyName}</p>
                      </div>
                      <span className={`text-xs font-medium ${contactColor}`}>{contactLabel}</span>
                    </div>
                  )
                })}

                {/* En cours d'enrichissement */}
                {Array.from(processingMap.values()).map(p => (
                  <div key={p.companyId} className="border border-slate-300 rounded-xl px-5 py-4 flex items-center gap-4">
                    <span className="w-4 h-4 border-2 border-brand-400 border-t-transparent rounded-full animate-spin shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900">{p.companyName}</p>
                      <p className="text-xs text-slate-500 mt-0.5">Recherche des contacts en ligne...</p>
                    </div>
                  </div>
                ))}

                {/* En attente */}
                {waitingCompanies.map(c => (
                  <div key={c.id} className="border border-slate-100 rounded-xl px-5 py-3.5 flex items-center gap-3 opacity-40">
                    <span className="w-4 h-4 rounded-full border-2 border-slate-300 shrink-0" />
                    <p className="text-sm font-medium text-slate-600">{c.name}</p>
                  </div>
                ))}

                {/* ── Sous-phases : enrichissement & vérification ── */}
                {(apolloPhase.state !== 'idle' || neverBouncePhase.state !== 'idle') && (
                  <div className="border border-slate-200 rounded-xl overflow-hidden mt-2">
                    <div className="px-5 py-3 bg-slate-50 border-b border-slate-200">
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Validation des contacts</p>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {apolloPhase.state !== 'idle' && (
                        <div className="px-5 py-3.5 flex items-center gap-3">
                          {apolloPhase.state === 'running' ? (
                            <span className="w-4 h-4 border-2 border-violet-400 border-t-transparent rounded-full animate-spin shrink-0" />
                          ) : (
                            <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                          )}
                          <div className="flex-1">
                            <p className="text-sm font-medium text-slate-800">Enrichissement supplémentaire</p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {apolloPhase.state === 'running'
                                ? `Recherche d'emails pour ${apolloPhase.total} contact(s)...`
                                : `${apolloPhase.filled} email(s) récupéré(s) sur ${apolloPhase.total} contact(s)`}
                            </p>
                          </div>
                        </div>
                      )}
                      {neverBouncePhase.state !== 'idle' && (
                        <div className="px-5 py-3.5 flex items-center gap-3">
                          {neverBouncePhase.state === 'running' ? (
                            <span className="w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full animate-spin shrink-0" />
                          ) : (
                            <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                          )}
                          <div className="flex-1">
                            <p className="text-sm font-medium text-slate-800">Vérification des adresses</p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {neverBouncePhase.state === 'running'
                                ? `Vérification de ${neverBouncePhase.total} email(s)...`
                                : `${neverBouncePhase.valid} email(s) valide(s)${neverBouncePhase.removed > 0 ? ` · ${neverBouncePhase.removed} supprimé(s)` : ''}`}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })()}

          {/* ── STEP 3: Rédaction ────────────── */}
          {pipelineStep === 3 && (
            <div className="p-8 space-y-3">
              <div className="mb-2">
                <h2 className="text-base font-bold text-slate-900 mb-1">Rédaction personnalisée</h2>
                <p className="text-sm text-slate-500">{blocks.length} / {paywallCount || companies.length} emails rédigés</p>
              </div>

              {/* Emails rédigés */}
              {blocks.map(b => (
                <div key={b.companyId} className="border border-emerald-100 bg-emerald-50/50 rounded-xl px-5 py-3.5 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    <p className="text-sm font-medium text-slate-800">{b.companyName}</p>
                  </div>
                  <span className="text-xs text-emerald-600 font-medium">{b.emails.length} email{b.emails.length > 1 ? 's' : ''}</span>
                </div>
              ))}

              {/* En cours de rédaction */}
              {Array.from(processingMap.values()).map(p => (
                <div key={p.companyId} className="border border-slate-300 rounded-xl px-5 py-4 flex items-center gap-4">
                  <span className="w-4 h-4 border-2 border-brand-400 border-t-transparent rounded-full animate-spin shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">{p.companyName}</p>
                    <p className="text-xs text-slate-500 mt-0.5">Rédaction du mail personnalisé...</p>
                  </div>
                </div>
              ))}

              {/* En attente de rédaction (enrichies mais pas encore traitées) */}
              {Array.from(enrichedCompanies.values()).map(e => (
                <div key={e.companyId} className="border border-slate-100 rounded-xl px-5 py-3.5 flex items-center gap-3 opacity-40">
                  <span className="w-4 h-4 rounded-full border-2 border-slate-300 shrink-0" />
                  <p className="text-sm font-medium text-slate-600">{e.companyName}</p>
                </div>
              ))}

              {!generating && processingMap.size === 0 && enrichedCompanies.size === 0 && (
                <div className="py-10 text-center">
                  <p className="text-sm font-medium text-slate-600">Rédaction terminée</p>
                  <p className="text-xs text-slate-500 mt-1">{draftEmails.length} email{draftEmails.length > 1 ? 's' : ''} prêt{draftEmails.length > 1 ? 's' : ''}</p>
                </div>
              )}
            </div>
          )}

          {/* ── STEP 4: Ready / Launched ─────── */}
          {pipelineStep === 4 && (
            <div className="p-8">
              <>
                  {/* Launched state */}
                  {isLaunched && (
                    <div className="space-y-5">
                      {campaign.totalEmails !== null && campaign.totalEmails > 0 && (
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs font-medium text-slate-600">Progression</span>
                            <span className="text-xs font-bold text-slate-900">{campaign.sentCount} / {campaign.totalEmails} mails</span>
                          </div>
                          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, (campaign.sentCount / campaign.totalEmails) * 100)}%` }} />
                          </div>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-50 rounded-xl px-4 py-3">
                          <p className="text-xs text-slate-600 mb-0.5">Restants</p>
                          <p className="text-lg font-bold text-slate-900">{(campaign.totalEmails ?? 0) - campaign.sentCount}</p>
                        </div>
                        <div className="bg-slate-50 rounded-xl px-4 py-3">
                          <p className="text-xs text-slate-600 mb-0.5">Limite / jour</p>
                          <p className="text-lg font-bold text-slate-900">{campaign.dailyLimit ?? '—'}</p>
                        </div>
                        <div className="bg-slate-50 rounded-xl px-4 py-3">
                          <p className="text-xs text-slate-600 mb-0.5">Fenêtre d&apos;envoi</p>
                          <p className="text-sm font-semibold text-slate-900">{fmtHour(campaign.sendStartHour)} – {fmtHour(campaign.sendEndHour)}</p>
                        </div>
                        {campaign.status === 'active' && (
                          <div className="bg-slate-50 rounded-xl px-4 py-3">
                            <p className="text-xs text-slate-600 mb-0.5">Prochain envoi</p>
                            <p className="text-sm font-semibold text-slate-900">{nextSendLabel()}</p>
                          </div>
                        )}
                      </div>

                      {/* Sent emails */}
                      <div className="pt-2">
                        <p className="text-xs font-medium text-slate-600 uppercase tracking-wide mb-3">
                          Mails envoyés {sentEmails.length > 0 && <span className="text-slate-600">({sentEmails.length})</span>}
                        </p>
                        {sentEmails.length === 0 ? (
                          <p className="text-sm text-slate-600 text-center py-8">
                            {campaign.status === 'active' ? 'Premier envoi imminent...' : 'Aucun mail envoyé'}
                          </p>
                        ) : (
                          <div className="space-y-1.5">
                            {sentEmails.map(email => (
                              <div key={email.id} className="flex items-center justify-between gap-3 py-2.5 border-b border-slate-200 last:border-0">
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm font-medium text-slate-800 truncate">{email.companyName}</p>
                                  <p className="text-xs text-slate-600 truncate">
                                    {email.recipientName && email.recipientName !== email.to && (
                                      <span className="mr-1.5">{email.recipientName}</span>
                                    )}
                                    {email.to && <span className="font-mono">{email.to}</span>}
                                  </p>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                  {email.sentAt && (
                                    <span className="text-xs text-slate-600">
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

                  {/* Pre-launch: review emails */}
                  {!isLaunched && (
                    <div className="space-y-5">
                      <div className="flex items-center justify-between">
                        <div>
                          <h2 className="text-base font-bold text-slate-900 mb-1">Prêt pour l&apos;envoi</h2>
                          <p className="text-sm text-slate-600">{draftEmails.length} email{draftEmails.length > 1 ? 's' : ''} en attente d&apos;envoi</p>
                        </div>
                        <button
                          onClick={() => setLaunchModalOpen(true)}
                          disabled={launchPending || draftEmails.length === 0}
                          className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors"
                        >
                          {launchPending ? 'Lancement programmé' : 'Lancer la campagne'}
                        </button>
                      </div>

                      {draftEmails.length === 0 ? (
                        <p className="text-sm text-slate-600 text-center py-12">
                          {generating ? "Les emails apparaîtront ici dès qu'ils sont générés" : 'Aucun email en attente'}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {blocks.filter(b => b.emails.some(e => e.status === 'draft')).map(block => {
                            const count = block.emails.filter(e => e.status === 'draft').length
                            return (
                              <button
                                key={block.companyId}
                                onClick={() => setSelectedCompanyId(block.companyId)}
                                className="w-full text-left border border-slate-300 hover:border-brand-200 rounded-xl px-5 py-4 flex items-center justify-between gap-3 transition-all hover:shadow-sm group bg-white"
                              >
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm font-medium text-slate-900 group-hover:text-brand-600 transition-colors truncate">{block.companyName}</p>
                                  {block.companyAddress && <p className="text-xs text-slate-600 truncate mt-0.5">{block.companyAddress}</p>}
                                </div>
                                <div className="flex items-center gap-2.5 shrink-0">
                                  <span className="text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-medium">
                                    {count} mail{count > 1 ? 's' : ''}
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
            </div>
          )}
        </div>

        {/* ── Right: Stats + Activity log ────── */}
        <div className="w-[340px] shrink-0 flex flex-col gap-4">
          {/* Metrics */}
          <div className="bg-white border border-slate-300 rounded-2xl px-5 py-4 shrink-0">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-4">Vue d&apos;ensemble</p>
            <div className="grid grid-cols-3 gap-0">
              <div className="flex flex-col items-center gap-1 py-1">
                <span className="text-2xl font-bold text-slate-900 tabular-nums">{companies.length}</span>
                <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider text-center leading-tight">Entreprises</span>
              </div>
              <div className="flex flex-col items-center gap-1 py-1 border-x border-slate-100">
                <span className="text-2xl font-bold text-slate-900 tabular-nums">{totalDecideurs}</span>
                <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider text-center leading-tight">Décideurs</span>
              </div>
              <div className="flex flex-col items-center gap-1 py-1">
                <span className="text-2xl font-bold text-slate-900 tabular-nums">{allEmails.length}</span>
                <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider text-center leading-tight">Emails</span>
              </div>
            </div>
          </div>
          {/* Activity log */}
          <div className="flex-1 min-h-0">
            <ActivityLog events={activityLog} />
          </div>
        </div>
      </div>

      {/* ── Company sidebar ─────────────────────── */}
      <CompanyDetailView
        block={selectedCompanyId ? (blocks.find(b => b.companyId === selectedCompanyId) ?? null) : null}
        campaignName={campaign.name}
        onClose={() => setSelectedCompanyId(null)}
        sending={sending}
        onSend={sendEmail}
      />

      {/* ── Modals ─────────────────────────────── */}
      <PaywallModal
        open={paywallOpen}
        totalCompanies={companies.length}
        onConfirm={(count) => { setPaywallCount(count); setPaywallOpen(false); setPreGenerateOpen(true) }}
        onCancel={() => setPaywallOpen(false)}
      />

      <PreGenerateModal
        open={preGenerateOpen}
        poolLimit={paywallCount || companies.length}
        onConfirm={handleGenerate}
        onCancel={() => setPreGenerateOpen(false)}
      />

      {launchModalOpen && (
        <LaunchModal
          campaignId={id}
          totalDraft={draftEmails.length}
          isGenerating={generating}
          onClose={() => setLaunchModalOpen(false)}
          onSuccess={handleLaunchSuccess}
        />
      )}

      {message && !scraping && pipelineStep !== 1 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 px-4 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-lg shadow-lg">
          {message}
        </div>
      )}
     </div>
    </div>
  )
}
