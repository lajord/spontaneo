'use client'

import { useState } from 'react'

type ConfigValues = {
  maxConcurrent: number
  batchSize: number
  pollIntervalMs: number
  modelEnrichissement: string
  modelEnrichissement2: string
  modelCreationMail: string
  modelCreationLm: string
  modelKeywords: string
  modelCvReader: string
  modelRanking: string
}

const MODEL_FIELDS: { key: keyof ConfigValues; label: string; description: string }[] = [
  { key: 'modelEnrichissement', label: 'Enrichissement (1)', description: 'Modele principal pour l\'enrichissement des entreprises (ex: spark-1-mini, gpt-5)' },
  { key: 'modelEnrichissement2', label: 'Enrichissement (2)', description: 'Modele secondaire pour l\'enrichissement (ex: sonar-pro, gemini-3.1-pro-preview)' },
  { key: 'modelCreationMail', label: 'Creation mail', description: 'Modele pour la generation des emails de candidature' },
  { key: 'modelCreationLm', label: 'Creation LM', description: 'Modele pour la generation des lettres de motivation' },
  { key: 'modelKeywords', label: 'Keywords', description: 'Modele pour l\'extraction de mots-cles de recherche' },
  { key: 'modelCvReader', label: 'Lecteur CV', description: 'Modele vision pour la lecture des CV (ex: Qwen2.5-VL-72B-Instruct)' },
  { key: 'modelRanking', label: 'Ranking / Filtre entreprises', description: 'Modele pour le classement des contacts et le filtrage des entreprises Apollo (ex: gemini-2.5-flash)' },
]

export default function AdminConfigForm({ defaultValues }: { defaultValues: ConfigValues }) {
  const [values, setValues] = useState<ConfigValues>(defaultValues)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    try {
      const res = await fetch('/api/admin/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      })

      if (res.ok) {
        const data = await res.json()
        setValues(data)
        setMessage({ type: 'success', text: 'Configuration sauvegardee. Les changements seront pris en compte au prochain cycle.' })
      } else {
        const data = await res.json()
        setMessage({ type: 'error', text: data.errors?.join(', ') || 'Erreur lors de la sauvegarde' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Erreur reseau' })
    } finally {
      setSaving(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'
  const numberInputClass = 'w-32 px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* ── Worker ────────────────────────────────────────────── */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-4">Parametres du Worker</h2>
        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Jobs paralleles max
            </label>
            <p className="text-xs text-slate-400 mb-2">
              Nombre maximum de jobs qui peuvent s'executer simultanement (1-10)
            </p>
            <input
              type="number"
              min={1}
              max={10}
              value={values.maxConcurrent}
              onChange={(e) => setValues({ ...values, maxConcurrent: parseInt(e.target.value) || 1 })}
              className={numberInputClass}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Taille du batch
            </label>
            <p className="text-xs text-slate-400 mb-2">
              Nombre d'entreprises traitees en parallele par job (1-20)
            </p>
            <input
              type="number"
              min={1}
              max={20}
              value={values.batchSize}
              onChange={(e) => setValues({ ...values, batchSize: parseInt(e.target.value) || 1 })}
              className={numberInputClass}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Intervalle de polling
            </label>
            <p className="text-xs text-slate-400 mb-2">
              Frequence a laquelle le worker verifie les nouveaux jobs, en secondes (5-120)
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={5}
                max={120}
                value={Math.round(values.pollIntervalMs / 1000)}
                onChange={(e) =>
                  setValues({ ...values, pollIntervalMs: (parseInt(e.target.value) || 5) * 1000 })
                }
                className={numberInputClass}
              />
              <span className="text-sm text-slate-400">secondes</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Modeles IA ────────────────────────────────────────── */}
      <div className="border-t border-slate-200 pt-6">
        <h2 className="text-sm font-semibold text-slate-700 mb-4">Modeles IA</h2>
        <div className="space-y-4">
          {MODEL_FIELDS.map(({ key, label, description }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {label}
              </label>
              <p className="text-xs text-slate-400 mb-2">{description}</p>
              <input
                type="text"
                value={(values as any)[key]}
                onChange={(e) => setValues({ ...values, [key]: e.target.value })}
                className={inputClass}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Feedback message */}
      {message && (
        <div
          className={`text-sm px-4 py-2.5 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={saving}
        className="inline-flex items-center gap-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
      >
        {saving ? 'Sauvegarde...' : 'Sauvegarder'}
      </button>
    </form>
  )
}
