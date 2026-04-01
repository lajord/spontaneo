'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

const SECTEURS: Record<string, { label: string; sousSecteurs: string[] }> = {
  cabinet_avocat: {
    label: 'Cabinet Avocat',
    sousSecteurs: [
      'Corporate M&A',
      'Droit Social',
      'Droit Fiscal',
      'Droit Penal',
      'IP / IT',
      'Banque & Finance',
      'Contentieux des Affaires',
      'Arbitrage',
      'Concurrence / Antitrust',
      'Private Equity',
      'Restructuring',
      'Droit Immobilier',
      'Droit Boursier',
      'Debt Finance',
    ],
  },
  banque: {
    label: 'Banque',
    sousSecteurs: [
      'Compliance',
      'M&A',
      'Financement Structure',
      'Trade Finance',
      'Wealth Management',
      'Risk Management',
      'Corporate Banking',
    ],
  },
  fond_investissement: {
    label: "Fond d'investissement",
    sousSecteurs: [
      'Private Equity',
      'Venture Capital',
      'Infrastructure',
      'Real Estate',
      'Debt Fund',
      'Growth Equity',
    ],
  },
}

type CsvRow = Record<string, string>
type LogLine = { text: string; color: string; costText?: string; totalText?: string }
type ActiveJobResponse = {
  job: null | {
    id: string
    status: string
    payload?: {
      jobTitle?: string
      location?: string
      secteur?: string
      sousSecteur?: string
    }
  }
}

const INPUT_COST_PER_MILLION_EUR = 3
const OUTPUT_COST_PER_MILLION_EUR = 15
const TOKEN_LOG_REGEX = /Tokens:\s*([\d,]+)\s+in\s*\|\s*([\d,]+)\s+out/i

function formatEuroAmount(amount: number): string {
  return amount.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function getTokenLogCost(message: string): number | null {
  const match = message.match(TOKEN_LOG_REGEX)
  if (!match) return null

  const inputTokens = Number(match[1].replace(/,/g, ''))
  const outputTokens = Number(match[2].replace(/,/g, ''))
  if (!Number.isFinite(inputTokens) || !Number.isFinite(outputTokens)) return null

  return (
    (inputTokens / 1_000_000) * INPUT_COST_PER_MILLION_EUR +
    (outputTokens / 1_000_000) * OUTPUT_COST_PER_MILLION_EUR
  )
}

function parseTokenLog(message: string, cumulativeCost: number): { text: string; costText?: string; totalText?: string } {
  const cost = getTokenLogCost(message)
  if (cost === null) return { text: message }

  return {
    text: message,
    costText: `${formatEuroAmount(cost)}€`,
    totalText: `Total = ${formatEuroAmount(cumulativeCost)}€`,
  }
}

export default function AgentPage() {
  const [jobTitle, setJobTitle] = useState('')
  const [location, setLocation] = useState('')
  const [secteur, setSecteur] = useState('cabinet_avocat')
  const [sousSecteur, setSousSecteur] = useState('')
  const [running, setRunning] = useState(false)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [candidates, setCandidates] = useState<CsvRow[]>([])
  const [enriched, setEnriched] = useState<CsvRow[]>([])
  const [csvTab, setCsvTab] = useState<'candidates' | 'enriched'>('candidates')

  const logsEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const sseStoppedRef = useRef(false)
  const cumulativeTokenCostRef = useRef(0)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const addLog = useCallback((text: string, color = '#d4d4d4') => {
    setLogs((prev) => [...prev, { text, color }])
  }, [])

  const stopStreaming = useCallback(() => {
    sseStoppedRef.current = true
    eventSourceRef.current?.close()
    eventSourceRef.current = null
  }, [])

  const handleEvent = useCallback((event: any) => {
    switch (event.type) {
      case 'config':
        addLog(
          `[CONFIG] ${event.secteur}${event.sous_secteur ? ` / ${event.sous_secteur}` : ''} / ${event.job_title} / ${event.location}`,
          '#60a5fa',
        )
        break
      case 'phase':
        addLog(`\n${'='.repeat(50)}`, '#34d399')
        addLog(`  ${event.message}`, '#34d399')
        addLog(`${'='.repeat(50)}`, '#34d399')
        break
      case 'log':
        {
          const rawMessage = String(event.message || '')
          const tokenCost = getTokenLogCost(rawMessage)
          if (tokenCost !== null) {
            cumulativeTokenCostRef.current += tokenCost
          }
          const parsed = parseTokenLog(rawMessage, cumulativeTokenCostRef.current)
          setLogs((prev) => [...prev, {
            text: `[${event.phase || 'LOG'}] ${parsed.text}`,
            color: '#d4d4d4',
            costText: parsed.costText,
            totalText: parsed.totalText,
          }])
        }
        break
      case 'tool_call':
        if (event.name === 'crawl_url') break
        addLog(`[TOOL] ${event.name}(${event.args})`, '#fbbf24')
        break
      case 'tool_result':
        break
      case 'progress':
        addLog(`[PROGRESS] ${event.message}`, '#a78bfa')
        break
      case 'csv_update':
        if (event.csv_type === 'candidates') setCandidates(event.rows || [])
        if (event.csv_type === 'enriched') setEnriched(event.rows || [])
        addLog(`[CSV] ${event.csv_type} mis a jour (${(event.rows || []).length} lignes)`, '#60a5fa')
        break
      case 'error':
        addLog(`[ERROR] ${event.message}`, '#ef4444')
        setRunning(false)
        setCurrentJobId(null)
        stopStreaming()
        break
      case 'stopped':
        addLog(`[STOPPED] ${event.message || 'Agent arrete.'}`, '#f97316')
        setRunning(false)
        setCurrentJobId(null)
        stopStreaming()
        break
      case 'cancelled':
        addLog(`[CANCELLED] ${event.message || 'Job annule.'}`, '#f97316')
        setRunning(false)
        setCurrentJobId(null)
        stopStreaming()
        break
      case 'complete':
        addLog('[FIN] Pipeline termine.', '#34d399')
        setRunning(false)
        setCurrentJobId(null)
        stopStreaming()
        break
      default:
        if (event.message) addLog(`[${event.type}] ${event.message}`, '#d4d4d4')
    }
  }, [addLog, stopStreaming])

  const connectToJob = useCallback((jobId: string) => {
    stopStreaming()
    sseStoppedRef.current = false
    setRunning(true)

    const es = new EventSource(`/api/jobs/${jobId}/events`)
    eventSourceRef.current = es

    es.onopen = () => {
      addLog(`[SSE] Connecte au job ${jobId}`, '#60a5fa')
    }

    es.onmessage = (message) => {
      try {
        handleEvent(JSON.parse(message.data))
      } catch {
        // ignore malformed payloads
      }
    }

    es.onerror = () => {
      if (sseStoppedRef.current) return
      addLog(`[SSE] Connexion interrompue pour ${jobId}`, '#f59e0b')
      setRunning(false)
      stopStreaming()
    }
  }, [addLog, handleEvent, stopStreaming])

  useEffect(() => {
    let cancelled = false

    const restoreActiveJob = async () => {
      try {
        const response = await fetch('/api/agent/job/active', { cache: 'no-store' })
        if (!response.ok) return

        const data = await response.json() as ActiveJobResponse
        const activeJob = data.job
        if (!activeJob || cancelled) return

        setCurrentJobId(activeJob.id)
        if (typeof activeJob.payload?.jobTitle === 'string') setJobTitle(activeJob.payload.jobTitle)
        if (typeof activeJob.payload?.location === 'string') setLocation(activeJob.payload.location)
        if (activeJob.payload?.secteur && SECTEURS[activeJob.payload.secteur]) {
          setSecteur(activeJob.payload.secteur)
        }
        if (typeof activeJob.payload?.sousSecteur === 'string') setSousSecteur(activeJob.payload.sousSecteur)

        cumulativeTokenCostRef.current = 0
        setLogs([{ text: `[RESUME] Reconnexion au job ${activeJob.id}`, color: '#60a5fa' }])
        connectToJob(activeJob.id)
      } catch {
        // ignore restore failures in dev page
      }
    }

    void restoreActiveJob()

    return () => {
      cancelled = true
    }
  }, [connectToJob])

  const handleSubmit = async () => {
    if (!jobTitle.trim() || !location.trim() || running) return

    const secteurLabel = SECTEURS[secteur]?.label || secteur
    setRunning(true)
    cumulativeTokenCostRef.current = 0
    setLogs([])
    setCandidates([])
    setEnriched([])
    addLog('[INIT] Creation du job agent', '#a855f7')
    addLog(
      `[START] ${secteurLabel}${sousSecteur ? ` / ${sousSecteur}` : ''} - ${jobTitle.trim()} - ${location.trim()}`,
      '#34d399',
    )

    try {
      const response = await fetch('/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          secteur,
          sous_secteur: sousSecteur || undefined,
          job_title: jobTitle.trim(),
          location: location.trim(),
        }),
      })

      if (!response.ok) {
        addLog(`[ERROR] HTTP ${response.status}`, '#ef4444')
        setRunning(false)
        return
      }

      const data = await response.json()
      if (!data?.jobId) {
        addLog('[ERROR] Aucun jobId recu', '#ef4444')
        setRunning(false)
        return
      }

      addLog(`[JOB] ${data.jobId} cree, attente du worker...`, '#60a5fa')
      setCurrentJobId(data.jobId)
      connectToJob(data.jobId)
    } catch (err: any) {
      addLog(`[ERROR] ${err.message}`, '#ef4444')
      setRunning(false)
    }
  }

  const handleStop = async () => {
    try {
      await fetch('/api/agent/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobId: currentJobId }),
      })
      addLog('[STOP] Annulation demandee.', '#f97316')
    } catch (err: any) {
      addLog(`[ERROR] ${err.message}`, '#ef4444')
    }
  }

  const displayedCsv = csvTab === 'candidates' ? candidates : enriched
  const csvColumns = csvTab === 'candidates'
    ? ['name', 'website_url', 'city', 'source', 'status']
    : ['company_name', 'contact_first_name', 'contact_last_name', 'contact_email', 'contact_title', 'source']

  return (
    <div className="p-6 max-w-[1600px] mx-auto w-full">
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Agent Recherche V2</h1>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Poste vise <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              disabled={running}
              placeholder="Ex: Juriste Compliance"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Ville <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={running}
              placeholder="Paris, Lyon, Bordeaux..."
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Secteur <span className="text-red-400">*</span>
            </label>
            <select
              value={secteur}
              onChange={(e) => {
                setSecteur(e.target.value)
                setSousSecteur('')
              }}
              disabled={running}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {Object.entries(SECTEURS).map(([key, value]) => (
                <option key={key} value={key}>{value.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Sous-secteur
            </label>
            <select
              value={sousSecteur}
              onChange={(e) => setSousSecteur(e.target.value)}
              disabled={running}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">- Aucun -</option>
              {SECTEURS[secteur]?.sousSecteurs.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-4 mt-4 justify-end">
          {running && (
            <button
              onClick={handleStop}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white shadow-sm transition-all"
            >
              Annuler le job
            </button>
          )}

          <button
            onClick={handleSubmit}
            disabled={running || !jobTitle.trim() || !location.trim()}
            className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${
              running || !jobTitle.trim() || !location.trim()
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-brand-600 hover:bg-brand-700 text-white shadow-sm'
            }`}
          >
            {running ? 'En cours...' : 'Lancer la recherche'}
          </button>
        </div>
      </div>

      <div className="bg-[#1e1e1e] border border-slate-700 rounded-xl p-4 mb-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-slate-400 text-xs ml-2 font-mono">Agent Logs</span>
          {running && <span className="ml-auto text-xs text-green-400 animate-pulse">Running...</span>}
        </div>
        <div className="font-mono text-xs leading-5 overflow-y-auto max-h-[400px] whitespace-pre-wrap" style={{ minHeight: '200px' }}>
          {logs.length === 0 && <span className="text-slate-500">En attente du lancement...</span>}
          {logs.map((line, index) => (
            <div key={index} style={{ color: line.color }}>
              {line.text}
              {line.costText && (
                <>
                  <span style={{ color: '#a78bfa' }}>{' => '}{line.costText}</span>
                  <span style={{ color: '#fbbf24', fontWeight: 700 }}>{' ; '}{line.totalText}</span>
                </>
              )}
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setCsvTab('candidates')}
            className={`px-5 py-3 text-sm font-medium transition-colors ${
              csvTab === 'candidates'
                ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/50'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Candidates ({candidates.length})
          </button>
          <button
            onClick={() => setCsvTab('enriched')}
            className={`px-5 py-3 text-sm font-medium transition-colors ${
              csvTab === 'enriched'
                ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/50'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Enriched ({enriched.length})
          </button>
          <div className="ml-auto px-4 py-3 text-xs text-slate-400">
            Source: JobEvent
          </div>
        </div>
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          {displayedCsv.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-400">Aucune donnee pour ce job.</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-500 w-8">#</th>
                  {csvColumns.map((column) => (
                    <th key={column} className="px-3 py-2 text-left font-medium text-slate-500">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedCsv.map((row, index) => (
                  <tr key={index} className="hover:bg-slate-50">
                    <td className="px-3 py-1.5 text-slate-400">{index + 1}</td>
                    {csvColumns.map((column) => (
                      <td key={column} className="px-3 py-1.5 text-slate-700 max-w-[300px] truncate">
                        {row[column] || ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
