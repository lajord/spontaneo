'use client'

import { useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

const SECTOR_TREE: Record<string, { label: string; subs: string[] }> = {
  technologie_numerique: {
    label: 'Technologie & Numérique',
    subs: ['ESN / services informatiques', 'éditeur de logiciel', 'startup tech', 'SaaS', 'cybersécurité', 'intelligence artificielle', 'cloud computing', 'data / big data', 'développement web', 'développement mobile', 'blockchain', 'fintech', 'legaltech', 'healthtech', 'insurtech', 'proptech', 'deeptech', 'devops', 'infrastructure IT', 'hébergement web', "éditeur d'applications", 'plateforme numérique'],
  },
  finance: {
    label: 'Finance',
    subs: ['banque', 'assurance', "gestion d'actifs", 'capital risque', 'private equity', 'fintech', 'courtage', 'audit', 'comptabilité', 'conseil financier', 'gestion de patrimoine', 'trading', 'paiement en ligne', 'néobanque', "fonds d'investissement", 'cabinet fiscal'],
  },
  conseil_services: {
    label: 'Conseil & Services aux entreprises',
    subs: ['cabinet de conseil', 'conseil en stratégie', 'conseil en management', 'conseil IT', 'conseil data', "cabinet d'audit", 'recrutement / RH', 'formation professionnelle', 'conseil juridique', "cabinet d'avocats", 'externalisation', 'BPO', 'conseil en innovation', 'conseil en transformation digitale', "coaching d'entreprise"],
  },
  marketing_communication: {
    label: 'Marketing & Communication',
    subs: ['agence marketing', 'agence digitale', 'agence SEO', 'publicité', 'relations publiques', 'média', 'production de contenu', "marketing d'influence", 'branding', 'communication corporate', 'agence événementielle', 'studio créatif', 'marketing automation', 'growth marketing'],
  },
  industrie: {
    label: 'Industrie',
    subs: ['industrie manufacturière', 'aéronautique', 'automobile', 'chimie', 'énergie', 'métallurgie', 'électronique', 'robotique', 'industrie pharmaceutique', 'plasturgie', 'textile', 'industrie lourde', 'fabrication de machines', 'équipements industriels', 'industrie du verre', 'industrie du bois'],
  },
  transport_logistique: {
    label: 'Transport & Logistique',
    subs: ['transport', 'logistique', 'supply chain', 'livraison', 'transport maritime', 'transport aérien', 'transport ferroviaire', 'transport routier', 'logistique e-commerce', 'entreposage', 'messagerie', 'transport international', 'gestion de flotte'],
  },
  commerce_distribution: {
    label: 'Commerce & Distribution',
    subs: ['e-commerce', 'grande distribution', 'retail', 'marketplace', 'commerce de gros', 'commerce de détail', 'supermarché', 'hypermarché', 'franchise', 'magasin spécialisé', 'vente en ligne', 'vente omnicanale'],
  },
  sante: {
    label: 'Santé',
    subs: ['hôpital', 'clinique', 'laboratoire', 'biotech', 'pharmaceutique', 'medtech', 'mutuelle', 'assurance santé', 'centre de recherche médical', 'télémédecine', 'dispositifs médicaux', 'centre de diagnostic', 'santé numérique'],
  },
  immobilier_construction: {
    label: 'Immobilier & Construction',
    subs: ['immobilier', 'promoteur immobilier', 'construction', 'BTP', 'architecture', 'urbanisme', 'agence immobilière', 'gestion immobilière', 'aménagement urbain', 'promotion immobilière', 'construction durable', 'ingénierie bâtiment'],
  },
  energie_environnement: {
    label: 'Énergie & Environnement',
    subs: ['énergie', 'pétrole', 'gaz', 'énergies renouvelables', 'nucléaire', 'environnement', 'recyclage', 'gestion des déchets', 'efficacité énergétique', 'énergie solaire', 'énergie éolienne', 'hydrogène', 'transition énergétique'],
  },
  agriculture_agroalimentaire: {
    label: 'Agriculture & Agroalimentaire',
    subs: ['agriculture', 'agroalimentaire', 'agritech', 'coopérative agricole', 'industrie alimentaire', 'production agricole', 'élevage', 'viticulture', 'distribution alimentaire', 'transformation alimentaire', 'agriculture biologique'],
  },
  tourisme_hotellerie: {
    label: 'Tourisme & Hôtellerie',
    subs: ['tourisme', 'agence de voyage', 'hôtel', 'hôtellerie', 'compagnie aérienne', 'événementiel', 'tour opérateur', 'location de vacances', 'parc de loisirs', 'croisière', "tourisme d'affaires"],
  },
  divertissement_medias: {
    label: 'Divertissement & Médias',
    subs: ['jeux vidéo', 'cinéma', 'production audiovisuelle', 'streaming', 'musique', 'médias', 'télévision', 'radio', 'édition', 'presse', 'plateforme de contenu', 'e-sport'],
  },
  education_recherche: {
    label: 'Éducation & Recherche',
    subs: ['université', 'école', 'edtech', 'formation', 'recherche', 'centre de recherche', 'formation en ligne', 'bootcamp', 'organisme de formation', 'institut académique'],
  },
  secteur_public: {
    label: 'Secteur public & Organisations',
    subs: ['administration', 'collectivité territoriale', 'ONG', 'association', 'organisation internationale', 'service public', 'organisation gouvernementale', 'institution publique', 'chambre de commerce'],
  },
}

const STEPS = [
  { num: 1, label: 'Informations' },
  { num: 2, label: 'Vérification' },
]

interface CvData {
  nom: string
  email: string
  telephone: string
  formation: string[]
  experience: string[]
  competences_brutes: string[]
  soft_skills: string[]
  langues: string[]
  poste_recherche: string
  secteur_recherche: string
  resume: string
}

export default function NewCampaignPage() {
  const router = useRouter()
  const cvFileInputRef = useRef<HTMLInputElement>(null)
  const lmFileInputRef = useRef<HTMLInputElement>(null)

  const [step, setStep] = useState(1)
  const [error, setError] = useState('')

  // Step 1
  const [name, setName] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [location, setLocation] = useState('')
  const [radius, setRadius] = useState(20)
  const [startDate, setStartDate] = useState('')
  const [durationValue, setDurationValue] = useState('')
  const [durationUnit, setDurationUnit] = useState('mois')
  const [cvFile, setCvFile] = useState<File | null>(null)
  const [lmFile, setLmFile] = useState<File | null>(null)
  const [prompt, setPrompt] = useState('')
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [sectors, setSectors] = useState<string[]>([])
  const [categorySearch, setCategorySearch] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  // Step 2
  const [cvData, setCvData] = useState<CvData | null>(null)
  const [lmText, setLmText] = useState('')
  const [cvFilename, setCvFilename] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const filteredCategories = Object.entries(SECTOR_TREE).filter(
    ([, v]) => v.label.toLowerCase().includes(categorySearch.toLowerCase())
  )

  function toggleCategory(key: string) {
    if (selectedCategories.includes(key)) {
      setSelectedCategories(selectedCategories.filter((k) => k !== key))
      // Remove all sub-sectors of this category
      const subs = SECTOR_TREE[key].subs
      setSectors(sectors.filter((s) => !subs.includes(s)))
    } else {
      setSelectedCategories([...selectedCategories, key])
    }
  }

  function toggleSubSector(sub: string) {
    if (sectors.includes(sub)) {
      setSectors(sectors.filter((s) => s !== sub))
    } else {
      setSectors([...sectors, sub])
    }
  }

  function step1Valid() {
    return !!(name && jobTitle && location && cvFile)
  }

  async function handleStep1Next() {
    if (!step1Valid()) return
    setIsAnalyzing(true)
    setError('')
    try {
      const [cvResult, lmResult] = await Promise.all([
        (async () => {
          const fd = new FormData()
          fd.append('cv', cvFile!)
          return (await fetch('/api/cv/extract', { method: 'POST', body: fd })).json()
        })(),
        lmFile
          ? (async () => {
            const fd = new FormData()
            fd.append('lm', lmFile)
            return (await fetch('/api/lm/analyze', { method: 'POST', body: fd })).json()
          })()
          : Promise.resolve(null),
      ])

      if (cvResult) {
        setCvData(cvResult)
        if (cvResult.cvFilename) setCvFilename(cvResult.cvFilename)
      }
      if (lmResult?.lm_text) setLmText(lmResult.lm_text)
      setStep(2)
    } catch {
      setError("Erreur lors de l'analyse des documents")
    } finally {
      setIsAnalyzing(false)
    }
  }

  async function createCampaign() {
    setCreating(true)
    setError('')
    const duration = durationValue ? `${durationValue} ${durationUnit}` : null
    try {
      const res = await fetch('/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          jobTitle,
          sectors,
          location,
          radius,
          startDate: startDate || null,
          duration,
          prompt: prompt || null,
          cvData: cvData ?? null,
          lmText: lmText || null,
          cvFilename: cvFilename || null,
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        setError(data.error ?? 'Erreur lors de la création')
        return
      }
      const campaign = await res.json()
      router.push(`/campaigns/${campaign.id}`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-50/30">

      {/* ── Barre d'onglets ───────────────────────────────────────────── */}
      <div className="bg-white border-b border-slate-200 px-4 pt-2.5 flex items-end gap-0.5 shrink-0">
        <div className="relative flex items-center gap-2 px-4 py-2 text-sm rounded-t-lg border-x border-t select-none bg-slate-50/30 border-slate-200 text-slate-900 font-medium -mb-px z-10 shadow-[0_1px_0_transparent]">
          Création
        </div>
      </div>

      {/* ── Contenu ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto w-full">
        <div className="max-w-3xl mx-auto my-8 bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">

          <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between gap-4 bg-white sticky top-0 z-10">
            <div>
              <h1 className="text-xl font-semibold text-slate-900 tracking-tight">Nouvelle campagne</h1>
              <p className="text-sm text-slate-500 mt-1">
                Étape {step} / {STEPS.length} — {STEPS[step - 1].label}
              </p>
            </div>
            <Link href="/dashboard" className="text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors bg-slate-50 hover:bg-slate-100 px-3 py-1.5 rounded-md border border-slate-200">
              Fermer
            </Link>
          </div>

          <div className="px-8 py-8 space-y-8">

            {/* ── Step 1 — Toutes les infos ─────────────────────────── */}
            {step === 1 && (
              <>
                {/* Nom de la campagne */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Nom de la campagne <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ex : Alternance dev web — Bordeaux 2025"
                    className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                  />
                </div>

                {/* Poste + Zone géographique */}
                <div className="space-y-4">
                  <h2 className="text-base font-medium text-slate-800 border-b border-slate-100 pb-2">Poste & Zone</h2>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1.5">
                      Poste / Secteur recherché <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={jobTitle}
                      onChange={(e) => setJobTitle(e.target.value)}
                      placeholder="Ex : Développeur React, Agence marketing, Cabinet RH..."
                      className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                    />
                  </div>

                  {/* Secteurs professionnels — sélection hiérarchique */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-sm font-medium text-slate-700">
                        Secteurs visés
                      </label>
                      <span className="text-xs text-slate-400">Optionnel</span>
                    </div>

                    {/* Recherche catégories */}
                    <input
                      type="text"
                      value={categorySearch}
                      onChange={(e) => setCategorySearch(e.target.value)}
                      placeholder="Rechercher un secteur..."
                      className="w-full border border-slate-200 rounded-lg px-3.5 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white mb-3"
                    />

                    {/* Grille catégories */}
                    <div className="flex flex-wrap gap-2">
                      {filteredCategories.map(([key, { label }]) => {
                        const isSelected = selectedCategories.includes(key)
                        return (
                          <button
                            key={key}
                            type="button"
                            onClick={() => toggleCategory(key)}
                            className={`text-xs font-medium rounded-full px-3 py-1.5 border transition-colors ${
                              isSelected
                                ? 'bg-brand-500 text-white border-brand-500'
                                : 'bg-white text-slate-600 border-slate-200 hover:border-brand-300 hover:text-brand-600'
                            }`}
                          >
                            {label}
                          </button>
                        )
                      })}
                    </div>

                    {/* Sous-secteurs pour chaque catégorie sélectionnée */}
                    {selectedCategories.length > 0 && (
                      <div className="mt-4 space-y-3">
                        {selectedCategories.map((catKey) => {
                          const cat = SECTOR_TREE[catKey]
                          if (!cat) return null
                          return (
                            <div key={catKey} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                                {cat.label}
                              </p>
                              <div className="flex flex-wrap gap-1.5">
                                {cat.subs.map((sub) => {
                                  const isActive = sectors.includes(sub)
                                  return (
                                    <button
                                      key={sub}
                                      type="button"
                                      onClick={() => toggleSubSector(sub)}
                                      className={`text-xs rounded-md px-2.5 py-1 border transition-colors ${
                                        isActive
                                          ? 'bg-brand-50 text-brand-700 border-brand-200 font-medium'
                                          : 'bg-white text-slate-600 border-slate-200 hover:border-brand-200 hover:text-brand-600'
                                      }`}
                                    >
                                      {sub}
                                    </button>
                                  )
                                })}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}

                    {/* Résumé des sous-secteurs sélectionnés */}
                    {sectors.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        <span className="text-xs text-slate-400 py-1 mr-1">{sectors.length} sélectionné{sectors.length > 1 ? 's' : ''} :</span>
                        {sectors.map((s) => (
                          <span
                            key={s}
                            className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 text-xs font-medium rounded-md px-2 py-1 border border-brand-200"
                          >
                            {s}
                            <button
                              type="button"
                              onClick={() => toggleSubSector(s)}
                              className="text-brand-400 hover:text-brand-600 ml-0.5"
                            >
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">
                        Ville / Zone <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        placeholder="Ex : Bordeaux"
                        className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Rayon (km)</label>
                      <input
                        type="number"
                        min={5}
                        max={100}
                        value={radius}
                        onChange={(e) => setRadius(parseInt(e.target.value))}
                        className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                      />
                    </div>
                  </div>
                </div>

                {/* Disponibilité */}
                <div className="space-y-4">
                  <h2 className="text-base font-medium text-slate-800 border-b border-slate-100 pb-2">
                    Disponibilité <span className="text-slate-400 font-normal">(optionnel)</span>
                  </h2>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Disponible à partir de</label>
                      <input
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">Durée</label>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min={1}
                          max={99}
                          value={durationValue}
                          onChange={(e) => setDurationValue(e.target.value)}
                          placeholder="Ex : 6"
                          className="w-20 border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                        />
                        <select
                          value={durationUnit}
                          onChange={(e) => setDurationUnit(e.target.value)}
                          className="flex-1 border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 transition bg-white"
                        >
                          <option value="semaine">semaine(s)</option>
                          <option value="mois">mois</option>
                          <option value="an">an(s)</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Documents CV & LM */}
                <div className="space-y-4">
                  <h2 className="text-base font-medium text-slate-800 border-b border-slate-100 pb-2">
                    Documents
                  </h2>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* CV */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1.5">
                        CV (PDF) <span className="text-red-500">*</span>
                      </label>
                      <div
                        onClick={() => cvFileInputRef.current?.click()}
                        className={`border border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors shadow-sm ${cvFile ? 'border-brand-400 bg-brand-50' : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50 bg-white'
                          }`}
                      >
                        <input
                          ref={cvFileInputRef}
                          type="file"
                          accept=".pdf"
                          className="hidden"
                          onChange={(e) => setCvFile(e.target.files?.[0] ?? null)}
                        />
                        {cvFile ? (
                          <div className="flex flex-col items-center gap-1.5">
                            <svg className="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-sm font-medium text-brand-700 truncate w-full px-2">{cvFile.name}</p>
                            <p className="text-xs text-brand-600/70">Modifier</p>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center gap-1.5">
                            <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            <p className="text-sm text-slate-600 font-medium">Importer un CV</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* LM */}
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <label className="block text-sm font-medium text-slate-700">Lettre de motivation</label>
                        <span className="text-xs text-slate-400">Optionnel</span>
                      </div>
                      <div
                        onClick={() => lmFileInputRef.current?.click()}
                        className={`border border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors shadow-sm ${lmFile ? 'border-brand-400 bg-brand-50' : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50 bg-white'
                          }`}
                      >
                        <input
                          ref={lmFileInputRef}
                          type="file"
                          accept=".pdf,.docx"
                          className="hidden"
                          onChange={(e) => setLmFile(e.target.files?.[0] ?? null)}
                        />
                        {lmFile ? (
                          <div className="flex flex-col items-center gap-1.5">
                            <svg className="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-sm font-medium text-brand-700 truncate w-full px-2">{lmFile.name}</p>
                            <p className="text-xs text-brand-600/70">Modifier</p>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center gap-1.5">
                            <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            <p className="text-sm text-slate-600 font-medium">Importer une LM</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 bg-amber-50/50 border border-amber-100/50 rounded-lg px-3 py-2 mt-2">
                    <svg className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-xs text-amber-700/80 leading-relaxed">
                      La lettre sera adaptée automatiquement pour chaque entreprise lors de la génération.
                    </p>
                  </div>
                </div>

                {/* Prompt contexte */}
                <div className="space-y-4">
                  <h2 className="text-base font-medium text-slate-800 border-b border-slate-100 pb-2">
                    Contexte & objectifs <span className="text-slate-400 font-normal">(optionnel)</span>
                  </h2>
                  <p className="text-sm text-slate-500">
                    Plus vous donnez d&apos;informations, plus les candidatures générées seront pertinentes. Décrivez votre situation, ce que vous cherchez, ce que vous souhaitez mettre en avant...
                  </p>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    rows={5}
                    placeholder="Ex : Je suis en 3ème année de BUT informatique, spécialité développement web. Je cherche une alternance de 12 mois à partir de septembre 2025 dans une agence web ou une startup tech sur Bordeaux. Je maîtrise React, Next.js et TypeScript, et j'ai fait un stage de 2 mois chez XYZ où j'ai travaillé sur leur refonte front-end. Je suis particulièrement intéressé par les entreprises qui font du produit..."
                    className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 transition resize-none bg-white"
                  />
                </div>

                {error && <p className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2.5">{error}</p>}

                <div className="flex gap-4 pt-4 border-t border-slate-100">
                  <Link
                    href="/dashboard"
                    className="flex-1 text-center border border-slate-200 rounded-lg py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    Annuler
                  </Link>
                  <button
                    type="button"
                    onClick={handleStep1Next}
                    disabled={!step1Valid() || isAnalyzing}
                    className="flex-1 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg py-2.5 text-sm transition-colors flex items-center justify-center gap-2"
                  >
                    {isAnalyzing ? (
                      <>
                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Analyse du CV en cours...
                      </>
                    ) : (
                      'Suivant →'
                    )}
                  </button>
                </div>
              </>
            )}

            {/* ── Step 2 — Vérification CV ──────────────────────────── */}
            {step === 2 && (
              <>
                <div className="border border-slate-200 rounded-xl p-6 bg-slate-50/30">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">Résumé du CV analysé</p>

                  {cvData ? (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        {cvData.nom && <span className="text-base font-semibold text-slate-900">{cvData.nom}</span>}
                        {cvData.poste_recherche && <span className="text-sm text-slate-500">{cvData.poste_recherche}</span>}
                        {cvData.email && <span className="text-xs text-slate-400">{cvData.email}</span>}
                        {cvData.telephone && <span className="text-xs text-slate-400">{cvData.telephone}</span>}
                      </div>

                      {cvData.resume && (
                        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
                          <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-1.5">Résumé IA</p>
                          <p className="text-sm text-slate-700 leading-relaxed">{cvData.resume}</p>
                        </div>
                      )}

                      {(cvData.competences_brutes ?? []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Compétences techniques</p>
                          <div className="flex flex-wrap gap-1.5">
                            {cvData.competences_brutes.slice(0, 10).map((c, i) => (
                              <span key={i} className="text-xs bg-brand-50 text-brand-700 rounded-full px-2.5 py-1">{c}</span>
                            ))}
                            {cvData.competences_brutes.length > 10 && (
                              <span className="text-xs text-slate-400 py-1">+{cvData.competences_brutes.length - 10} autres</span>
                            )}
                          </div>
                        </div>
                      )}

                      {(cvData.soft_skills ?? []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Soft skills</p>
                          <div className="flex flex-wrap gap-1.5">
                            {cvData.soft_skills.map((s, i) => (
                              <span key={i} className="text-xs bg-slate-100 text-slate-700 rounded-full px-2.5 py-1">{s}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {(cvData.experience ?? []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Expériences</p>
                          <ul className="space-y-1">
                            {cvData.experience.map((e, i) => (
                              <li key={i} className="text-sm text-slate-700 flex gap-2">
                                <span className="text-slate-400 mt-0.5">•</span>{e}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(cvData.formation ?? []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Formation</p>
                          <ul className="space-y-1">
                            {cvData.formation.map((f, i) => (
                              <li key={i} className="text-sm text-slate-700 flex gap-2">
                                <span className="text-slate-400 mt-0.5">•</span>{f}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(cvData.langues ?? []).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Langues</p>
                          <div className="flex flex-wrap gap-1.5">
                            {cvData.langues.map((l, i) => (
                              <span key={i} className="text-xs bg-slate-100 text-slate-700 rounded-full px-2.5 py-1">{l}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {lmText && (
                        <div className="flex items-center gap-2 bg-green-50 border border-green-100 rounded-lg px-3.5 py-2.5">
                          <svg className="w-4 h-4 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <p className="text-xs text-green-700">
                            Lettre de motivation chargée — elle sera adaptée automatiquement pour chaque entreprise.
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-10">
                      <svg className="w-10 h-10 text-slate-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <p className="text-sm text-slate-500">Aucun CV analysé</p>
                    </div>
                  )}
                </div>

                {error && <p className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2.5">{error}</p>}

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    disabled={creating}
                    className="flex-1 border border-slate-200 rounded-lg py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
                  >
                    ← Précédent
                  </button>
                  <button
                    type="button"
                    onClick={createCampaign}
                    disabled={creating}
                    className="flex-1 bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
                  >
                    {creating ? 'Création...' : 'Créer la campagne'}
                  </button>
                </div>
              </>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}
