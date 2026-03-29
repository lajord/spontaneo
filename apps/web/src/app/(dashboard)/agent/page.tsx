'use client'

import { useState, useRef, useEffect, useCallback } from 'react'

const ROLES: Record<number, string> = { 1: 'Banques', 2: "Cabinets d'Avocats", 3: 'Fonds / Investissement' }

const SPECIALTIES_BY_ROLE: Record<number, Record<number, string>> = {
  1: {
    1: 'Juriste Droit Bancaire',
    2: 'Juriste Financier',
    3: 'Juriste Contentieux',
    4: 'Juriste Compliance',
    5: 'Juriste Corporate / M&A',
  },
  2: {
    1: 'Contentieux des Affaires',
    2: 'Arbitrage',
    3: 'Concurrence / Antitrust',
    4: 'Distribution & Consommation',
    5: 'IP / IT',
    6: 'Droit Fiscal',
    7: 'Droit Boursier',
    8: 'Debt Finance',
    9: 'Corporate M&A / Fusions-Acquisitions',
    10: 'Restructuring / Entreprises en difficulté',
    11: 'Private Equity / Capital-Investissement',
    12: 'Droit Immobilier / Real Estate',
    13: 'Financement de Projets',
    14: 'Banque & Finance',
    15: 'Droit Social',
    16: 'Droit Pénal',
  },
  3: {
    1: 'Private Equity / Capital-investissement',
    2: 'Venture Capital / Capital-risque',
    3: 'Dette privée',
    4: 'Immobilier',
    5: 'Infrastructure',
    6: 'Fonds de fonds',
    7: 'Impact / ESG',
    8: 'Situations spéciales / Distressed',
  }
}

interface CsvRow {
  [key: string]: string
}

type LogLine = { text: string; color: string }

export default function AgentPage() {
  const [role, setRole] = useState(2)
  const [specialtyNum, setSpecialtyNum] = useState(1)
  const [location, setLocation] = useState('')
  const [targetCount, setTargetCount] = useState(50)
  const [extra, setExtra] = useState('')

  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [candidates, setCandidates] = useState<CsvRow[]>([])
  const [verified, setVerified] = useState<CsvRow[]>([])
  const [enriched, setEnriched] = useState<CsvRow[]>([])
  const [csvTab, setCsvTab] = useState<'candidates' | 'enriched'>('candidates')

  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const addLog = useCallback((text: string, color: string = '#d4d4d4') => {
    setLogs(prev => [...prev, { text, color }])
  }, [])

  const handleStop = async () => {
    try {
      await fetch('/api/agent/stop', { method: 'POST' })
      addLog('[STOP] Arrêt forcé demandé — CSV vidés.', '#f97316')
      setCandidates([])
      setVerified([])
      setEnriched([])
    } catch (err: any) {
      addLog(`[ERROR] ${err.message}`, '#ef4444')
    }
  }

  const handleSubmit = async () => {
    if (!location.trim() || running) return

    setRunning(true)
    setLogs([])
    setCandidates([])
    setVerified([])
    setEnriched([])

    const body = {
      role,
      specialty_num: specialtyNum,
      location: location.trim(),
      target_count: targetCount,
      extra: extra.trim(),
    }

    const specName = SPECIALTIES_BY_ROLE[role]?.[specialtyNum] || 'Général'

    addLog(
      `[INIT] 🚀 Démarrage du nouvel Agent V1 (apps/agent)`,
      '#a855f7', // Purple color for visibility
    )
    addLog(
      `[START] ${ROLES[role]} — ${specName} — ${location} — ${targetCount} entités`,
      '#34d399',
    )

    try {
      const response = await fetch('/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok || !response.body) {
        addLog(`[ERROR] HTTP ${response.status}`, '#ef4444')
        setRunning(false)
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            handleEvent(event)
          } catch {
            /* ignore parse errors */
          }
        }
      }
    } catch (err: any) {
      addLog(`[ERROR] ${err.message}`, '#ef4444')
    } finally {
      setRunning(false)
      addLog('[FIN] Pipeline terminé.', '#34d399')
      fetchCsv('candidates')
      fetchCsv('enriched')
    }
  }

  const handleEvent = useCallback(
    (event: any) => {
      switch (event.type) {
        case 'config':
          addLog(
            `[CONFIG] ${event.role} / ${event.specialty} / ${event.location} / ${event.target_count}`,
            '#60a5fa',
          )
          break
        case 'phase':
          addLog(`\n${'='.repeat(50)}`, '#34d399')
          addLog(`  ${event.message}`, '#34d399')
          addLog(`${'='.repeat(50)}`, '#34d399')
          break
        case 'log':
          addLog(`[${event.phase || 'LOG'}] ${event.message}`, '#d4d4d4')
          break
        case 'tool_call':
          addLog(`[TOOL] ${event.name}(${event.args})`, '#fbbf24')
          break
        case 'tool_result':
          addLog(`[RESULT] ${event.message}`, '#9ca3af')
          break
        case 'progress':
          addLog(`[PROGRESS] ${event.message}`, '#a78bfa')
          break
        case 'csv_update':
          if (event.csv_type === 'candidates') setCandidates(event.rows || [])
          else if (event.csv_type === 'verified') setVerified(event.rows || [])
          else if (event.csv_type === 'enriched') setEnriched(event.rows || [])
          addLog(
            `[CSV] ${event.csv_type} mis à jour (${(event.rows || []).length} lignes)`,
            '#60a5fa',
          )
          break
        case 'error':
          addLog(`[ERROR] ${event.message}`, '#ef4444')
          break
        case 'stopped':
          addLog(`[STOPPED] ${event.message || 'Agent arrêté.'}`, '#f97316')
          break
        case 'done':
          addLog(`[DONE] ${event.message}`, '#34d399')
          break
        default:
          if (event.message) addLog(`[${event.type}] ${event.message}`, '#d4d4d4')
      }
    },
    [addLog],
  )

  const fetchCsv = async (type: 'candidates' | 'verified' | 'enriched') => {
    try {
      const res = await fetch(`/api/agent/csv/${type}`)
      const data = await res.json()
      if (type === 'candidates') setCandidates(data.rows || [])
      else if (type === 'verified') setVerified(data.rows || [])
      else if (type === 'enriched') setEnriched(data.rows || [])
    } catch {
      /* ignore */
    }
  }

  const displayedCsv = csvTab === 'candidates' ? candidates : enriched
  const csvColumns =
    csvTab === 'candidates'
      ? ['name', 'website_url', 'city', 'source', 'status']
      : ['company_name', 'contact_first_name', 'contact_last_name', 'contact_email', 'contact_title', 'source']

  return (
    <div className="p-6 max-w-[1600px] mx-auto w-full">
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Agent Recherche V1</h1>
        <span className="bg-purple-100 text-purple-700 text-xs px-2.5 py-1 rounded-full font-medium">Nouvelle Architecture</span>
      </div>

      {/* Formulaire */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Cible / Secteur</label>
            <select
              value={role}
              onChange={e => {
                const newRole = Number(e.target.value)
                setRole(newRole)
                const firstSpec = Object.keys(SPECIALTIES_BY_ROLE[newRole])[0]
                if (firstSpec) setSpecialtyNum(Number(firstSpec))
              }}
              disabled={running}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {Object.entries(ROLES).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Spécialité / Poste</label>
            <select
              value={specialtyNum}
              onChange={e => setSpecialtyNum(Number(e.target.value))}
              disabled={running}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
            >
              {Object.entries(SPECIALTIES_BY_ROLE[role] || {}).map(([k, name]) => (
                <option key={k} value={k}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Ville</label>
            <input
              type="text"
              value={location}
              onChange={e => setLocation(e.target.value)}
              disabled={running}
              placeholder="Paris, Lyon, Bordeaux..."
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Nombre de cabinets</label>
            <input
              type="number"
              value={targetCount}
              onChange={e => setTargetCount(Number(e.target.value) || 50)}
              disabled={running}
              min={1}
              max={500}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="flex gap-4 mt-4 items-end">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-500 mb-1">Precisions (optionnel)</label>
            <input
              type="text"
              value={extra}
              onChange={e => setExtra(e.target.value)}
              disabled={running}
              placeholder="Ex: cabinets de moins de 50 personnes..."
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={running || !location.trim()}
            className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${
              running
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-brand-600 hover:bg-brand-700 text-white shadow-sm'
            }`}
          >
            {running ? 'En cours...' : 'Lancer la recherche'}
          </button>
          {running && (
            <button
              onClick={handleStop}
              className="px-6 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white shadow-sm transition-all"
            >
              Forcer l'arret
            </button>
          )}
        </div>
      </div>

      {/* Terminal Logs */}
      <div className="bg-[#1e1e1e] border border-slate-700 rounded-xl p-4 mb-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-slate-400 text-xs ml-2 font-mono">Agent Logs</span>
          {running && <span className="ml-auto text-xs text-green-400 animate-pulse">Running...</span>}
        </div>
        <div
          className="font-mono text-xs leading-5 overflow-y-auto max-h-[400px] whitespace-pre-wrap"
          style={{ minHeight: '200px' }}
        >
          {logs.length === 0 && <span className="text-slate-500">En attente du lancement...</span>}
          {logs.map((line, i) => (
            <div key={i} style={{ color: line.color }}>
              {line.text}
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* CSV Tables */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => {
              setCsvTab('candidates')
              fetchCsv('candidates')
            }}
            className={`px-5 py-3 text-sm font-medium transition-colors ${
              csvTab === 'candidates'
                ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/50'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Candidates ({candidates.length})
          </button>
          <button
            onClick={() => {
              setCsvTab('enriched')
              fetchCsv('enriched')
            }}
            className={`px-5 py-3 text-sm font-medium transition-colors ${
              csvTab === 'enriched'
                ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/50'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Enriched ({enriched.length})
          </button>
          <button
            onClick={() => fetchCsv(csvTab)}
            className="ml-auto px-4 py-3 text-xs text-slate-400 hover:text-slate-600"
          >
            Rafraichir
          </button>
        </div>
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          {displayedCsv.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-400">Aucune donnee. Lancez une recherche.</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-500 w-8">#</th>
                  {csvColumns.map(col => (
                    <th key={col} className="px-3 py-2 text-left font-medium text-slate-500">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedCsv.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-3 py-1.5 text-slate-400">{i + 1}</td>
                    {csvColumns.map(col => (
                      <td key={col} className="px-3 py-1.5 text-slate-700 max-w-[300px] truncate">
                        {col === 'website_url' && row[col] ? (
                          <a href={row[col]} target="_blank" rel="noopener" className="text-brand-600 hover:underline">
                            {row[col]}
                          </a>
                        ) : (
                          row[col] || ''
                        )}
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
