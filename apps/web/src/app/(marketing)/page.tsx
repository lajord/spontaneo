'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search, MapPin, ArrowRight, CheckCircle,
  Crosshair, Zap, Mail, Clock, Shield, BarChart2,
} from 'lucide-react'

const DOMAINS = ['Tech & IT', 'Finance', 'Marketing', 'Conseil', 'Droit', 'RH', 'Communication', 'Santé']

const STEPS = [
  {
    num: '01',
    title: 'Créez votre campagne',
    desc: 'Renseignez votre poste, secteur et localisation. Uploadez votre CV en 2 minutes.',
  },
  {
    num: '02',
    title: "Nos algorithmes trouvent les cibles",
    desc: 'Nos algorithmes analysent des milliers de sources pour identifier les entreprises les plus pertinentes.',
  },
  {
    num: '03',
    title: 'Les candidatures partent',
    desc: 'Chaque mail est personnalisé avec le bon contact, votre CV et une lettre de motivation sur mesure.',
  },
]

const FEATURES = [
  { icon: Crosshair, title: 'Ciblage intelligent',        desc: 'Nos algorithmes croisent de multiples sources pour trouver exactement les entreprises qui correspondent à votre profil.' },
  { icon: Zap,       title: 'Enrichissement automatique', desc: 'Notre IA identifie automatiquement le bon interlocuteur et ses coordonnées dans chaque entreprise ciblée.' },
  { icon: Mail,      title: 'Mails ultra-personnalisés',  desc: "Chaque email est rédigé sur mesure. Jamais de template générique — notre IA s'adapte à chaque entreprise." },
  { icon: Clock,     title: 'Envoi planifié',             desc: 'Les mails partent en semaine, entre 8h et 18h, avec des quotas pour maximiser vos chances de réponse.' },
  { icon: Shield,    title: 'Anti-doublon garanti',       desc: 'Nos systèmes s\'assurent de ne jamais contacter deux fois la même entreprise. Votre réputation est protégée.' },
  { icon: BarChart2, title: 'Dashboard temps réel',       desc: 'Suivez vos campagnes en live : entreprises analysées, mails envoyés, statuts de réponse.' },
]

const STATS = [
  { value: '2 400+',  label: 'Candidatures envoyées' },
  { value: '68 %',    label: "Taux d'ouverture moyen" },
  { value: '3×',      label: "Plus d'entretiens décrochés" },
  { value: '100 %', label: 'Mails personnalisés' },
]

export default function LandingPage() {
  const router = useRouter()
  const [jobTitle, setJobTitle] = useState('')
  const [city, setCity] = useState('')
  const [selectedDomain, setSelectedDomain] = useState('')

  // Scroll reveal
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('is-visible') }),
      { threshold: 0.1 }
    )
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  function handleSearch() {
    const params = new URLSearchParams()
    if (jobTitle.trim()) params.set('jobTitle', jobTitle.trim())
    if (city.trim()) params.set('location', city.trim())
    if (selectedDomain) params.set('domain', selectedDomain)
    const qs = params.toString()
    router.push(`/register${qs ? `?${qs}` : ''}`)
  }

  return (
    <>

      {/* ══════════════════════════════════════════════════════
          HERO
      ══════════════════════════════════════════════════════ */}
      <section
        className="relative flex flex-col items-center justify-center px-6 py-24 overflow-hidden"
        style={{
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #fafaf5 0%, #d4e8cf 25%, #9ec49a 50%, #b8c9ba 75%, #d6d6d2 100%)',
        }}
      >

        <div className="relative w-full max-w-[640px] mx-auto text-center">

          {/* Badge */}
          <div className="lp-a0 inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-emerald-200 bg-emerald-50 mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[11px] font-semibold text-emerald-700 tracking-widest uppercase">
              Candidatures automatisées par IA
            </span>
          </div>

          {/* Headline */}
          <h1 className="lp-a1 font-bold tracking-tight leading-[1.06] text-gray-950 mb-5"
            style={{ fontSize: 'clamp(40px, 6vw, 64px)' }}>
            Automatisez votre
            <br />
            <span style={{ color: '#0891b2' }}>recherche d'emploi.</span>
          </h1>

          {/* Subtitle */}
          <p className="lp-a2 text-[16px] text-gray-700 max-w-[420px] mx-auto leading-relaxed mb-10">
            Envoyez des dizaines de candidatures spontanées hyper-personnalisées chaque semaine, sans lever le petit doigt.
          </p>

          {/* Search card */}
          <div
            className="lp-a3 rounded-2xl p-4 text-left"
            style={{
              background: '#fff',
              border: '1px solid rgba(0,0,0,0.07)',
              boxShadow: '0 4px 6px -2px rgba(0,0,0,0.04), 0 20px 50px -8px rgba(0,0,0,0.09)',
            }}
          >
            <div className="flex flex-col sm:flex-row gap-2">

              {/* Job title */}
              <div className="flex-1 flex items-center gap-2.5 rounded-xl px-4 py-3 border border-gray-100 bg-gray-50 focus-within:border-emerald-300 focus-within:bg-white transition-all group">
                <Search className="w-4 h-4 shrink-0 text-gray-300 group-focus-within:text-emerald-500 transition-colors" />
                <input
                  type="text"
                  value={jobTitle}
                  onChange={e => setJobTitle(e.target.value)}
                  placeholder="Quel poste ? Ex: Chef de projet, Analyste, Juriste..."
                  className="flex-1 bg-transparent text-gray-900 placeholder:text-gray-400 text-sm outline-none"
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                />
              </div>

              {/* City */}
              <div className="sm:w-40 flex items-center gap-2.5 rounded-xl px-4 py-3 border border-gray-100 bg-gray-50 focus-within:border-emerald-300 focus-within:bg-white transition-all group">
                <MapPin className="w-4 h-4 shrink-0 text-gray-300 group-focus-within:text-emerald-500 transition-colors" />
                <input
                  type="text"
                  value={city}
                  onChange={e => setCity(e.target.value)}
                  placeholder="Paris"
                  className="min-w-0 w-full bg-transparent text-gray-900 placeholder:text-gray-400 text-sm outline-none"
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                />
              </div>
            </div>

            {/* Domains */}
            <div className="mt-3.5">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2.5">Domaine</p>
              <div className="flex flex-wrap gap-1.5">
                {DOMAINS.map(d => (
                  <button
                    key={d}
                    onClick={() => setSelectedDomain(prev => prev === d ? '' : d)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-150 hover:scale-[1.03] active:scale-[0.97]"
                    style={selectedDomain === d
                      ? { background: '#ecfdf5', borderColor: '#6ee7b7', color: '#059669' }
                      : { background: '#f9fafb', borderColor: '#e5e7eb', color: '#6b7280' }
                    }
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* CTA */}
            <button
              onClick={handleSearch}
              className="mt-4 w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-white text-sm font-semibold transition-all duration-200 hover:scale-[1.01] active:scale-[0.99] hover:brightness-110"
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                boxShadow: '0 4px 20px rgba(16,185,129,0.28)',
              }}
            >
              Lancer la recherche
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          {/* Trust */}
          <div className="lp-a4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 mt-7 text-xs text-gray-600">
            <span className="flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5 text-emerald-500" />Gratuit pour commencer</span>
            <span className="w-px h-3 bg-gray-200 hidden sm:block" />
            <span className="flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5 text-emerald-500" />Aucune carte requise</span>
            <span className="w-px h-3 bg-gray-200 hidden sm:block" />
            <span className="flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5 text-emerald-500" />Setup simple et guidé</span>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          STATS
      ══════════════════════════════════════════════════════ */}
      <section className="py-16 border-y border-gray-100" style={{ background: '#f9fafb' }}>
        <div className="max-w-4xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {STATS.map((s, i) => (
            <div key={i} className={`reveal reveal-delay-${i + 1}`}>
              <div
                className="text-[40px] md:text-[48px] font-bold tracking-tight leading-none mb-2 text-gray-950"
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                {s.value}
              </div>
              <div className="text-sm text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          HOW IT WORKS
      ══════════════════════════════════════════════════════ */}
      <section className="py-28 bg-white">
        <div className="max-w-5xl mx-auto px-6">

          <div className="reveal text-center mb-16">
            <p className="text-xs font-semibold text-emerald-600 uppercase tracking-widest mb-3">Comment ça marche</p>
            <h2 className="font-bold text-gray-950 tracking-tight leading-[1.1]"
              style={{ fontSize: 'clamp(28px, 4vw, 44px)' }}>
              De zéro à des dizaines de candidatures<br />
              <span className="text-gray-400 font-semibold">en toute simplicité.</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-5">
            {STEPS.map((s, i) => (
              <div
                key={i}
                className={`reveal reveal-delay-${i + 1} relative rounded-2xl p-7 border border-gray-100 bg-white group hover:border-emerald-200 hover:-translate-y-1 transition-all duration-300`}
                style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
              >
                <div className="text-[11px] font-bold text-emerald-500 tracking-widest mb-5">{s.num}</div>
                <h3 className="text-[17px] font-bold text-gray-950 mb-2 group-hover:text-emerald-700 transition-colors">{s.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{s.desc}</p>
                <div className="absolute bottom-0 left-6 right-6 h-[2px] rounded-full bg-gradient-to-r from-emerald-400/0 via-emerald-400/50 to-emerald-400/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          FEATURES
      ══════════════════════════════════════════════════════ */}
      <section className="py-28 border-t border-gray-100" style={{ background: '#f9fafb' }}>
        <div className="max-w-5xl mx-auto px-6">

          <div className="reveal text-center mb-16">
            <p className="text-xs font-semibold text-emerald-600 uppercase tracking-widest mb-3">Fonctionnalités</p>
            <h2 className="font-bold text-gray-950 tracking-tight leading-[1.1]"
              style={{ fontSize: 'clamp(28px, 4vw, 44px)' }}>
              Tout ce dont vous avez besoin,<br />
              <span className="text-gray-400 font-semibold">rien de superflu.</span>
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            {FEATURES.map((f, i) => {
              const Icon = f.icon
              return (
                <div
                  key={i}
                  className={`reveal reveal-delay-${(i % 3) + 1} bg-white rounded-2xl p-6 border border-gray-100 group hover:border-emerald-200 hover:shadow-md hover:-translate-y-0.5 transition-all duration-300`}
                  style={{ boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}
                >
                  <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center mb-4 group-hover:bg-emerald-100 transition-colors">
                    <Icon className="w-[18px] h-[18px] text-emerald-600" />
                  </div>
                  <h3 className="text-[15px] font-bold text-gray-900 mb-1.5">{f.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          FINAL CTA
      ══════════════════════════════════════════════════════ */}
      <section className="relative py-32 overflow-hidden" style={{ background: '#0d1117' }}>
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(16,185,129,0.09) 0%, transparent 100%)' }}
        />
        <div
          className="absolute top-0 left-0 right-0 h-px"
          style={{ background: 'linear-gradient(90deg, transparent, rgba(16,185,129,0.45), transparent)' }}
        />

        <div className="reveal relative max-w-xl mx-auto px-6 text-center">
          <p className="text-xs font-semibold text-emerald-400 uppercase tracking-widest mb-5">Commencez maintenant</p>
          <h2 className="font-bold text-white tracking-tight leading-[1.08] mb-5"
            style={{ fontSize: 'clamp(32px, 4.5vw, 52px)' }}>
            Votre prochain entretien
            <br />
            <span className="lp-shimmer">commence ici.</span>
          </h2>
          <p className="text-[15px] text-white/40 mb-10 max-w-sm mx-auto">
            Rejoignez les professionnels qui laissent l'IA travailler pour eux.
          </p>
          <button
            onClick={() => router.push('/register')}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-white text-sm font-semibold transition-all duration-200 hover:scale-[1.02] hover:brightness-110 active:scale-[0.99]"
            style={{
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              boxShadow: '0 4px 30px rgba(16,185,129,0.35)',
            }}
          >
            Créer mon compte gratuitement
            <ArrowRight className="w-4 h-4" />
          </button>
          <p className="mt-4 text-xs text-white/20">Aucune carte bancaire · Accès immédiat</p>
        </div>
      </section>

    </>
  )
}
