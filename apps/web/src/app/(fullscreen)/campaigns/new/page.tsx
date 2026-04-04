'use client'

import { useState, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import DatePicker from '@/components/DatePicker'

const SECTOR_TREE: Record<string, { label: string; subs: string[] }> = {
  technologie_numerique: {
    label: 'Tech & IT',
    subs: ['ESN / services informatiques', 'éditeur de logiciel', 'startup tech', 'SaaS', 'cybersécurité', 'intelligence artificielle', 'cloud computing', 'data / big data', 'développement web', 'développement mobile', 'blockchain', 'fintech', 'legaltech', 'healthtech', 'insurtech', 'proptech', 'deeptech', 'devops', 'infrastructure IT', 'hébergement web', "éditeur d'applications", 'plateforme numérique'],
  },
  finance: {
    label: 'Finance',
    subs: ['banque', 'assurance', "gestion d'actifs", 'capital risque', 'private equity', 'fintech', 'courtage', 'audit', 'comptabilité', 'conseil financier', 'gestion de patrimoine', 'trading', 'paiement en ligne', 'néobanque', "fonds d'investissement", 'cabinet fiscal'],
  },
  conseil_services: {
    label: 'Conseil & Services',
    subs: ['cabinet de conseil', 'conseil en stratégie', 'conseil en management', 'conseil IT', 'conseil data', "cabinet d'audit", 'recrutement / RH', 'formation professionnelle', 'conseil juridique', "cabinet d'avocats", 'externalisation', 'BPO', 'conseil en innovation', 'conseil en transformation digitale', "coaching d'entreprise"],
  },
  marketing_communication: {
    label: 'Marketing',
    subs: ['agence marketing', 'agence digitale', 'agence SEO', 'publicité', 'relations publiques', 'média', 'production de contenu', "marketing d'influence", 'branding', 'communication corporate', 'agence événementielle', 'studio créatif', 'marketing automation', 'growth marketing'],
  },
  communication: {
    label: 'Communication',
    subs: ['relations publiques', 'communication corporate', 'agence événementielle', 'journalisme', 'médias', 'édition'],
  },
  ressources_humaines: {
    label: 'Ressources Humaines',
    subs: ['recrutement', 'formation professionnelle', 'coaching', 'intérim', 'gestion de la paie'],
  },
  droit: {
    label: 'Droit',
    subs: ["cabinet d'avocats", 'conseil juridique', 'notariat', 'huissier', 'juriste d\'entreprise'],
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
    label: 'Commerce & Retail',
    subs: ['e-commerce', 'grande distribution', 'retail', 'marketplace', 'commerce de gros', 'commerce de détail', 'supermarché', 'hypermarché', 'franchise', 'magasin spécialisé', 'vente en ligne', 'vente omnicanale'],
  },
  sante: {
    label: 'Santé',
    subs: ['hôpital', 'clinique', 'laboratoire', 'biotech', 'pharmaceutique', 'medtech', 'mutuelle', 'assurance santé', 'centre de recherche médical', 'télémédecine', 'dispositifs médicaux', 'centre de diagnostic', 'santé numérique'],
  },
  immobilier_construction: {
    label: 'Immo & Construction',
    subs: ['immobilier', 'promoteur immobilier', 'construction', 'BTP', 'architecture', 'urbanisme', 'agence immobilière', 'gestion immobilière', 'aménagement urbain', 'promotion immobilière', 'construction durable', 'ingénierie bâtiment'],
  },
  energie_environnement: {
    label: 'Énergie & Env.',
    subs: ['énergie', 'pétrole', 'gaz', 'énergies renouvelables', 'nucléaire', 'environnement', 'recyclage', 'gestion des déchets', 'efficacité énergétique', 'énergie solaire', 'énergie éolienne', 'hydrogène', 'transition énergétique'],
  },
  agriculture_agroalimentaire: {
    label: 'Agriculture & Agro.',
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
    label: 'Éducation',
    subs: ['université', 'école', 'edtech', 'formation', 'recherche', 'centre de recherche', 'formation en ligne', 'bootcamp', 'organisme de formation', 'institut académique'],
  },
  secteur_public: {
    label: 'Secteur public & ONG',
    subs: ['administration', 'collectivité territoriale', 'ONG', 'association', 'organisation internationale', 'service public', 'organisation gouvernementale', 'institution publique', 'chambre de commerce'],
  },
}

const CONTRACT_TYPES = ['CDI', 'CDD', 'Stage', 'Alternance', 'Freelance', 'Intérim']
const LEGAL_DOMAINS = ['Banque', "Cabinet d'avocats", "Fond d'investissement"] as const

const STEPS = [
  { num: 1, label: 'Poste' },
  { num: 2, label: 'Localisation' },
  { num: 3, label: 'Documents' },
  { num: 4, label: 'Récapitulatif' },
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
  const [direction, setDirection] = useState<'forward' | 'backward'>('forward')
  const [animKey, setAnimKey] = useState(0)
  const [error, setError] = useState('')

  // Step 1
  const [jobTitle, setJobTitle] = useState('')
  const [targetDomain, setTargetDomain] = useState<(typeof LEGAL_DOMAINS)[number] | ''>('')
  const [contractType, setContractType] = useState('')
  const [startDate, setStartDate] = useState('')
  const [durationValue, setDurationValue] = useState('')
  const [durationUnit, setDurationUnit] = useState('mois')

  // Step 2
  const [filterPrompt, setFilterPrompt] = useState('')

  // Step 2
  const [location, setLocation] = useState('')
  const [radius, setRadius] = useState(20)

  // Step 3
  const [cvFile, setCvFile] = useState<File | null>(null)
  const [lmFile, setLmFile] = useState<File | null>(null)
  const [lmTextRaw, setLmTextRaw] = useState('')

  // Step 4
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [cvData, setCvData] = useState<CvData | null>(null)
  const [lmText, setLmText] = useState('')
  const [cvFilename, setCvFilename] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const campaignName = `${jobTitle || 'Recherche'} — ${location || 'France'}`

  const goForward = useCallback((nextStep: number) => {
    setDirection('forward')
    setAnimKey(k => k + 1)
    setStep(nextStep)
  }, [])

  const goBackward = useCallback((nextStep: number) => {
    setDirection('backward')
    setAnimKey(k => k + 1)
    setStep(nextStep)
  }, [])

  function selectContract(type: string) {
    setContractType(prev => prev === type ? '' : type)
  }

  function canProceed(currentStep: number) {
    if (currentStep === 1) return jobTitle.trim().length > 0 && targetDomain.length > 0
    if (currentStep === 2) return location.trim().length > 0
    if (currentStep === 3) return cvFile !== null
    return true
  }

  async function goToRecapAndAnalyze() {
    if (!cvFile) return
    setIsAnalyzing(true)
    setError('')
    goForward(4)

    try {
      const fd = new FormData()
      fd.append('cv', cvFile)
      const cvResult = await (await fetch('/api/cv/extract', { method: 'POST', body: fd })).json()
      let lmResultObj = null

      if (lmFile) {
        const lf = new FormData()
        lf.append('lm', lmFile)
        lmResultObj = await (await fetch('/api/lm/analyze', { method: 'POST', body: lf })).json()
      } else if (lmTextRaw.trim().length > 0) {
        lmResultObj = { lm_text: lmTextRaw.trim() }
      }

      if (cvResult) {
        setCvData(cvResult)
        if (cvResult.cvFilename) setCvFilename(cvResult.cvFilename)
      }
      if (lmResultObj?.lm_text) setLmText(lmResultObj.lm_text)
    } catch {
      setError("Erreur lors de l'analyse des documents")
    } finally {
      setIsAnalyzing(false)
    }
  }

  function handleNext() {
    if (step === 3) {
      goToRecapAndAnalyze()
    } else if (step < 4) {
      goForward(step + 1)
    }
  }

  function handleBack() {
    if (step > 1) {
      if (step === 4) {
        setCvData(null)
        setLmText('')
        setError('')
      }
      goBackward(step - 1)
    }
  }

  async function createCampaign() {
    setCreating(true)
    setError('')

    const duration = durationValue ? `${durationValue} ${durationUnit}` : null
    let builtPrompt = ''
    if (contractType) {
      builtPrompt += `Type de contrat recherché : ${contractType}. `
    }
    if (filterPrompt.trim()) {
      builtPrompt += `\nCritères de sélection des entreprises : ${filterPrompt.trim()}`
    }

    try {
      const res = await fetch('/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: campaignName,
          jobTitle,
          sectors: [],
          categories: targetDomain ? [targetDomain] : [],
          location,
          radius,
          startDate: startDate || null,
          duration,
          prompt: builtPrompt.trim() || null,
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
    <div className="min-h-screen bg-white flex flex-col items-center relative overflow-x-hidden">

      {/* Back button */}
      <Link
        href="/dashboard"
        className="fixed top-6 left-6 z-50 flex items-center gap-2 text-[13px] font-medium text-neutral-400 hover:text-neutral-900 transition-all duration-200 group"
      >
        <svg className="w-4 h-4 transition-transform duration-200 group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        Retour
      </Link>

      {/* Stepper */}
      <div className="w-full max-w-4xl mt-16 mb-12 px-6">
        <div className="flex items-center w-full">
          {STEPS.map((s, i) => {
            const isCompleted = step > s.num
            const isActive = step === s.num
            return (
              <div key={s.num} className="flex items-center flex-1 last:flex-none">
                <div className="flex items-center gap-2.5 shrink-0">
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center text-[12px] font-semibold transition-all duration-300
                    ${isCompleted ? 'bg-brand-500 text-white shadow-sm shadow-brand-500/25' :
                      isActive ? 'bg-neutral-900 text-white shadow-sm shadow-neutral-900/20' : 'bg-neutral-100 text-neutral-400'}`}
                  >
                    {isCompleted ? (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : s.num}
                  </div>
                  <span className={`text-[13px] font-medium whitespace-nowrap transition-colors duration-300 ${isActive ? 'text-neutral-900' : isCompleted ? 'text-brand-600' : 'text-neutral-400'}`}>
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 mx-4 h-[2px] transition-colors duration-500 ${step > s.num ? 'bg-brand-300' : 'bg-neutral-200'}`} />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Form content — animated */}
      <div
        key={animKey}
        className={`w-full max-w-4xl flex-1 px-6 ${direction === 'forward' ? 'step-forward' : 'step-backward'}`}
      >

        {/* Step 1: Poste */}
        {step === 1 && (
          <div className="space-y-8">
            <div className="mb-8">
              <h1 className="text-2xl font-semibold text-neutral-900 mb-1.5 tracking-tight">Quel poste en droit recherchez-vous ?</h1>
              <p className="text-neutral-600 text-sm">Indiquez un intitulé juridique précis pour cibler les bonnes opportunités.</p>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-2.5">
                Intitulé du poste en droit
              </label>
              <input
                type="text"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                autoFocus
                placeholder="Ex : Juriste droit des affaires, Avocat M&A, Compliance Officer..."
                className="w-full border border-neutral-300 bg-white px-4 py-2.5 text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-all duration-200 text-[15px] font-medium rounded-lg"
              />
            </div>

            <div className="pt-2">
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">
                Domaine
              </label>
              <div className="flex flex-wrap gap-2">
                {LEGAL_DOMAINS.map((domain) => {
                  const isSelected = targetDomain === domain
                  return (
                    <button
                      key={domain}
                      type="button"
                      onClick={() => setTargetDomain(domain)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 border ${
                        isSelected
                          ? 'bg-[#20293C] text-white border-[#20293C] shadow-sm'
                          : 'bg-transparent text-neutral-700 border-neutral-300 hover:border-[#20293C] hover:text-[#20293C] hover:shadow-sm'
                      }`}
                    >
                      {domain}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="pt-2">
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">
                Type de contrat
              </label>
              <div className="flex flex-wrap gap-2">
                {CONTRACT_TYPES.map((type) => {
                  const isSelected = contractType === type
                  return (
                    <button
                      key={type}
                      onClick={() => selectContract(type)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 border ${
                        isSelected
                          ? 'bg-[#20293C] text-white border-[#20293C] shadow-sm'
                          : 'bg-transparent text-neutral-700 border-neutral-300 hover:border-[#20293C] hover:text-[#20293C] hover:shadow-sm'
                      }`}
                    >
                      {type}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-8 pt-4">
              <div>
                <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-2.5">
                  Disponible dès le
                  <span className="normal-case tracking-normal font-normal text-neutral-400 ml-1">(optionnel)</span>
                </label>
                <DatePicker
                  value={startDate}
                  onChange={setStartDate}
                  placeholder="Sélectionner une date"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-2.5">
                  Durée
                  <span className="normal-case tracking-normal font-normal text-neutral-400 ml-1">(optionnel)</span>
                </label>
                <div className="flex gap-3 items-center">
                  <input
                    type="number"
                    min={1}
                    max={99}
                    value={durationValue}
                    onChange={(e) => setDurationValue(e.target.value)}
                    placeholder="6"
                    className="w-20 border border-neutral-300 bg-white px-3 py-2.5 text-neutral-900 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-all duration-200 text-sm font-medium rounded-lg text-center"
                  />
                  <div className="flex rounded-lg border border-neutral-300 overflow-hidden">
                    {(['semaine', 'mois', 'an'] as const).map((unit) => (
                      <button
                        key={unit}
                        type="button"
                        onClick={() => setDurationUnit(unit)}
                        className={`px-3.5 py-2 text-sm font-medium transition-all duration-200 ${
                          durationUnit === unit
                            ? 'bg-[#20293C] text-white'
                            : 'bg-white text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                        }`}
                      >
                        {unit === 'semaine' ? 'Sem.' : unit === 'mois' ? 'Mois' : 'An'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Localisation */}
        {step === 2 && (
          <div className="space-y-8">
            <div className="mb-8">
              <h1 className="text-2xl font-semibold text-neutral-900 mb-1.5 tracking-tight">Où souhaitez-vous travailler ?</h1>
              <p className="text-neutral-600 text-sm">Indiquez la ville et le rayon de recherche.</p>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-2.5">
                Ville / Zone
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                autoFocus
                placeholder="Ex : Paris, Lyon, Bordeaux..."
                className="w-full border border-neutral-300 bg-white px-4 py-3 text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-all duration-200 text-lg font-medium rounded-lg"
              />
            </div>

            <div className="pt-2">
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-2.5">
                Rayon de recherche
              </label>
              <div className="max-w-[160px]">
                <div className="relative">
                  <input
                    type="number"
                    min={1}
                    max={200}
                    step={5}
                    value={radius}
                    onChange={(e) => setRadius(parseInt(e.target.value))}
                    className="w-full border border-neutral-300 bg-white px-4 py-2.5 pr-12 text-neutral-900 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-all duration-200 text-[15px] font-medium rounded-lg"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-neutral-500 text-sm font-medium">km</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Documents */}
        {step === 3 && (
          <div className="space-y-8">
            <div className="mb-8">
              <h1 className="text-2xl font-semibold text-neutral-900 mb-1.5 tracking-tight">Vos documents</h1>
              <p className="text-neutral-600 text-sm">Importez votre CV et lettre de motivation.</p>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">
                CV (PDF) <span className="text-brand-500">*</span>
              </label>
              <button
                type="button"
                onClick={() => cvFileInputRef.current?.click()}
                className={`w-full p-7 border rounded-lg flex flex-col items-center justify-center transition-all duration-200 ${
                  cvFile
                    ? 'border-brand-400 bg-brand-50/60 shadow-sm'
                    : 'border-neutral-300 bg-white hover:border-neutral-900 hover:shadow-sm'
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
                  <>
                    <svg className="w-5 h-5 mb-2.5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span className="text-sm font-semibold text-neutral-900 truncate max-w-sm">{cvFile.name}</span>
                    <span className="text-[11px] text-brand-600 mt-2 uppercase tracking-wide font-semibold">Modifier</span>
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5 mb-2.5 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                    <span className="text-sm text-neutral-700 font-medium">Cliquez pour importer votre CV</span>
                  </>
                )}
              </button>
            </div>

            <div className="pt-2">
              <label className="block text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">
                Lettre de motivation
                <span className="normal-case tracking-normal font-normal text-neutral-400 ml-1">(optionnel)</span>
              </label>

              <button
                type="button"
                onClick={() => lmFileInputRef.current?.click()}
                className={`w-full p-6 border rounded-lg flex flex-col items-center justify-center transition-all duration-200 ${
                  lmFile
                    ? 'border-neutral-900 bg-neutral-50 shadow-sm'
                    : 'border-neutral-300 bg-white hover:border-neutral-900 hover:shadow-sm'
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
                  <>
                    <svg className="w-4 h-4 mb-2 text-neutral-900" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    <span className="text-sm font-semibold text-neutral-900 truncate max-w-sm">{lmFile.name}</span>
                    <span className="text-[11px] text-neutral-500 mt-2 uppercase tracking-wide font-semibold">Modifier</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mb-2 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    <span className="text-sm text-neutral-700 font-medium">Importer un document</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Recap */}
        {step === 4 && (
          <div className="space-y-8">
            {isAnalyzing ? (
              <div className="py-20 flex flex-col items-center justify-center text-center">
                <div className="w-8 h-8 border-2 border-neutral-200 border-t-neutral-900 rounded-full animate-spin mb-6"></div>
                <h2 className="text-lg font-semibold text-neutral-900 mb-1">Analyse de votre profil</h2>
                <p className="text-neutral-600 text-sm">L'intelligence artificielle synthétise vos données...</p>
              </div>
            ) : cvData ? (
              <div className="space-y-7">
                <div className="mb-8">
                  <h1 className="text-2xl font-semibold text-neutral-900 mb-1.5 tracking-tight">Récapitulatif</h1>
                  <p className="text-neutral-600 text-sm">Vérifiez les informations avant de lancer votre campagne.</p>
                </div>

                {/* Candidat + contact */}
                <div className="border border-neutral-300 rounded-lg p-6 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold text-neutral-900 tracking-tight">{cvData.nom || 'Candidat'}</h3>
                    <p className="text-neutral-600 mt-0.5 uppercase tracking-wide text-[11px] font-semibold">{cvData.poste_recherche || jobTitle}</p>
                  </div>
                  <div className="flex flex-col gap-1 text-sm text-neutral-800 font-medium">
                    {cvData.email && <span>{cvData.email}</span>}
                    {cvData.telephone && <span>{cvData.telephone}</span>}
                  </div>
                </div>

                {/* Critères de recherche */}
                <div>
                  <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">Critères de recherche</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="border border-neutral-200 rounded-lg p-3.5">
                      <span className="block text-[10px] font-semibold text-neutral-400 uppercase tracking-wide mb-1">Poste</span>
                      <span className="text-sm font-semibold text-neutral-900">{jobTitle}</span>
                    </div>
                    <div className="border border-neutral-200 rounded-lg p-3.5">
                      <span className="block text-[10px] font-semibold text-neutral-400 uppercase tracking-wide mb-1">Domaine</span>
                      <span className="text-sm font-semibold text-neutral-900">{targetDomain}</span>
                    </div>
                    {contractType && (
                      <div className="border border-neutral-200 rounded-lg p-3.5">
                        <span className="block text-[10px] font-semibold text-neutral-400 uppercase tracking-wide mb-1">Contrat</span>
                        <span className="text-sm font-semibold text-neutral-900">{contractType}</span>
                      </div>
                    )}
                    <div className="border border-neutral-200 rounded-lg p-3.5">
                      <span className="block text-[10px] font-semibold text-neutral-400 uppercase tracking-wide mb-1">Localisation</span>
                      <span className="text-sm font-semibold text-neutral-900">{location} <span className="text-neutral-400 font-medium">({radius} km)</span></span>
                    </div>
                    {startDate && (
                      <div className="border border-neutral-200 rounded-lg p-3.5">
                        <span className="block text-[10px] font-semibold text-neutral-400 uppercase tracking-wide mb-1">Disponible dès</span>
                        <span className="text-sm font-semibold text-neutral-900">{new Date(startDate).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
                      </div>
                    )}
                    {durationValue && (
                      <div className="border border-neutral-200 rounded-lg p-3.5">
                        <span className="block text-[10px] font-semibold text-neutral-400 uppercase tracking-wide mb-1">Durée</span>
                        <span className="text-sm font-semibold text-neutral-900">{durationValue} {durationUnit}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Domaine ciblé */}
                {targetDomain && (
                  <div>
                    <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">Domaine ciblé</h4>
                    <div className="flex flex-wrap gap-2">
                      <span className="text-[12px] border border-brand-300 px-2.5 py-1 rounded-md text-brand-800 bg-brand-50/50 font-medium">{targetDomain}</span>
                    </div>
                  </div>
                )}

                {/* Résumé CV */}
                {cvData.resume && (
                  <div>
                    <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-2.5">Résumé du profil</h4>
                    <p className="text-sm text-neutral-900 leading-relaxed font-medium">{cvData.resume}</p>
                  </div>
                )}

                {/* Skills */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  {(cvData.competences_brutes ?? []).length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">Hard skills</h4>
                      <div className="flex flex-wrap gap-2">
                        {cvData.competences_brutes.slice(0, 12).map((c, i) => (
                          <span key={i} className="text-[12px] border border-neutral-300 px-2.5 py-1 rounded-md text-neutral-900 bg-neutral-50 font-medium">{c}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {(cvData.soft_skills ?? []).length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">Soft skills</h4>
                      <div className="flex flex-wrap gap-2">
                        {cvData.soft_skills.map((s, i) => (
                          <span key={i} className="text-[12px] border border-brand-300 px-2.5 py-1 rounded-md text-brand-800 bg-brand-50/50 font-medium">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Documents */}
                <div>
                  <h4 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.08em] mb-3">Documents</h4>
                  <div className="flex flex-wrap gap-3">
                    <div className="flex items-center gap-2 border border-neutral-200 rounded-lg px-3.5 py-2.5">
                      <svg className="w-4 h-4 text-brand-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <span className="text-sm font-medium text-neutral-900">CV importé</span>
                    </div>
                    {lmText ? (
                      <div className="flex items-center gap-2 border border-neutral-200 rounded-lg px-3.5 py-2.5">
                        <svg className="w-4 h-4 text-brand-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        <span className="text-sm font-medium text-neutral-900">Lettre de motivation intégrée</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 border border-dashed border-neutral-200 rounded-lg px-3.5 py-2.5">
                        <span className="text-sm font-medium text-neutral-400">Pas de lettre de motivation</span>
                      </div>
                    )}
                  </div>
                </div>

                {error && <div className="p-4 bg-red-50 text-red-600 text-sm font-semibold border border-red-200 rounded-lg">{error}</div>}
              </div>
            ) : (
              <div className="py-20 text-center border border-dashed border-neutral-300 rounded-lg">
                <p className="text-base font-semibold text-neutral-900 mb-1">Analyse échouée</p>
                <p className="text-sm text-neutral-600 font-medium">Le système n'a pas pu traiter votre fichier CV.</p>
                {error && <p className="mt-3 text-xs text-red-500 font-medium">{error}</p>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div className="w-full max-w-4xl mt-10 mb-8 pt-5 border-t border-neutral-100 flex items-center justify-between px-6">
        <button
          onClick={handleBack}
          className={`px-5 py-2.5 text-xs font-semibold uppercase tracking-[0.06em] transition-all duration-200 rounded-lg ${
            step > 1 && !isAnalyzing && !creating
              ? 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50'
              : 'text-transparent cursor-default pointer-events-none'
          }`}
          disabled={step === 1 || isAnalyzing || creating}
        >
          Retour
        </button>

        {step < 4 ? (
          <button
            onClick={handleNext}
            disabled={!canProceed(step)}
            className="px-7 py-2.5 bg-neutral-900 hover:bg-neutral-800 disabled:bg-neutral-200 disabled:text-neutral-400 text-white text-xs font-semibold uppercase tracking-[0.06em] transition-all duration-200 flex items-center gap-2.5 rounded-lg hover:shadow-md"
          >
            Continuer
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
          </button>
        ) : (
          <button
            onClick={createCampaign}
            disabled={isAnalyzing || creating || !cvData}
            className="px-7 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-neutral-200 disabled:text-neutral-400 text-white text-xs font-semibold uppercase tracking-[0.06em] transition-all duration-200 flex items-center gap-2.5 rounded-lg hover:shadow-md"
          >
            {creating ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                Lancement...
              </>
            ) : (
              'Activer la recherche'
            )}
          </button>
        )}
      </div>
    </div>
  )
}
