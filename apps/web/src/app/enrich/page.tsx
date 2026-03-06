'use client'

import { useState } from 'react'

interface Contact {
  nom?: string
  prenom?: string
  role?: string
  email?: string
}

interface Company {
  nom: string
  adresse?: string
  site_web?: string
  telephone?: string
}

interface EnrichedCompany extends Company {
  emails: string[]
  dirigeant?: Contact | null
  rh?: Contact | null
  autres_contacts: Contact[]
}

type GranularityLevel = 'faible' | 'moyen' | 'fort'

const GRANULARITY_OPTIONS: { value: GranularityLevel; label: string; description: string }[] = [
  { value: 'faible', label: 'Faible', description: 'Recherche précise' },
  { value: 'moyen',  label: 'Moyen',  description: 'Recherche équilibrée' },
  { value: 'fort',   label: 'Fort',   description: 'Recherche large' },
]

interface SearchResult {
  secteur: string
  localisation: string
  total: number
  entreprises: Company[]
}

// État d'enrichissement par entreprise
type EnrichState = 'idle' | 'loading' | 'done' | 'error'

interface CompanyState {
  enrichState: EnrichState
  data?: EnrichedCompany
}

export default function EnrichPage() {
  const [secteur, setSecteur] = useState('')
  const [localisation, setLocalisation] = useState('')
  const [granularite, setGranularite] = useState<GranularityLevel>('moyen')
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [companyStates, setCompanyStates] = useState<Record<number, CompanyState>>({})

  // ── Recherche Google Places ───────────────────────────────────────────────
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    setSearching(true)
    setSearchError(null)
    setResult(null)
    setCompanyStates({})

    try {
      const res = await fetch('/api/enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secteur, localisation, granularite }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Erreur serveur')
      setResult(data)
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setSearching(false)
    }
  }

  // ── Enrichissement Perplexity pour une entreprise ────────────────────────
  const handleEnrich = async (company: Company, index: number) => {
    setCompanyStates(prev => ({ ...prev, [index]: { enrichState: 'loading' } }))

    try {
      const res = await fetch('/api/enrich/company', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nom: company.nom,
          site_web: company.site_web,
          adresse: company.adresse,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Erreur')
      setCompanyStates(prev => ({ ...prev, [index]: { enrichState: 'done', data } }))
    } catch {
      setCompanyStates(prev => ({ ...prev, [index]: { enrichState: 'error' } }))
    }
  }

  return (
    <main style={s.main}>
      <h1 style={s.title}>Recherche de contacts</h1>
      <p style={s.desc}>Google Places + Perplexity — à la demande, par entreprise</p>

      {/* Formulaire */}
      <form onSubmit={handleSearch} style={s.form}>
        <div style={s.row}>
          <div style={s.field}>
            <label style={s.label}>Secteur / Métier</label>
            <input style={s.input} value={secteur} onChange={e => setSecteur(e.target.value)}
              placeholder="Cabinet d'avocats, E-commerce..." required />
          </div>
          <div style={s.field}>
            <label style={s.label}>Ville / Région</label>
            <input style={s.input} value={localisation} onChange={e => setLocalisation(e.target.value)}
              placeholder="Paris, Lyon, 75001..." required />
          </div>
        </div>
        <div style={s.granularityGroup}>
          {GRANULARITY_OPTIONS.map(opt => (
            <button key={opt.value} type="button" onClick={() => setGranularite(opt.value)}
              style={{ ...s.granularityBtn, ...(granularite === opt.value ? s.granularityBtnActive : {}) }}>
              <span style={s.granularityLabel}>{opt.label}</span>
              <span style={s.granularityDesc}>{opt.description}</span>
            </button>
          ))}
        </div>

        <button type="submit" disabled={searching}
          style={{ ...s.btn, opacity: searching ? 0.7 : 1, cursor: searching ? 'not-allowed' : 'pointer' }}>
          {searching ? 'Recherche en cours...' : 'Rechercher'}
        </button>
      </form>

      {searchError && <div style={s.error}>{searchError}</div>}

      {/* Résultats */}
      {result && (
        <div style={s.results}>
          <p style={s.total}>
            {result.total} entreprise{result.total > 1 ? 's' : ''} — cliquez sur
            <strong> "Trouver contacts"</strong> pour enrichir
          </p>

          {result.entreprises.map((company, i) => {
            const state = companyStates[i] ?? { enrichState: 'idle' }
            const enriched = state.data

            return (
              <div key={i} style={s.card}>
                {/* Header */}
                <div style={s.cardHead}>
                  <div>
                    <h3 style={s.companyName}>{company.nom}</h3>
                    {company.adresse && <p style={s.meta}>{company.adresse}</p>}
                    {company.telephone && <p style={s.meta}>📞 {company.telephone}</p>}
                    {company.site_web && (
                      <a href={company.site_web} target="_blank" rel="noopener noreferrer" style={s.siteLink}>
                        {company.site_web.replace(/^https?:\/\//, '')}
                      </a>
                    )}
                  </div>

                  {/* Bouton enrichissement */}
                  {state.enrichState === 'idle' && (
                    <button onClick={() => handleEnrich(company, i)} style={s.enrichBtn}>
                      Trouver contacts
                    </button>
                  )}
                  {state.enrichState === 'loading' && (
                    <span style={s.loadingBadge}>Recherche...</span>
                  )}
                  {state.enrichState === 'error' && (
                    <button onClick={() => handleEnrich(company, i)} style={{ ...s.enrichBtn, backgroundColor: '#fee', color: '#c00', borderColor: '#c00' }}>
                      Réessayer
                    </button>
                  )}
                </div>

                {/* Résultats Perplexity */}
                {state.enrichState === 'done' && enriched && (
                  <div style={s.enrichResult}>
                    {enriched.emails.length > 0 && (
                      <div style={s.section}>
                        <span style={s.sectionLabel}>Emails</span>
                        <div style={s.emailList}>
                          {enriched.emails.map(email => (
                            <a key={email} href={`mailto:${email}`} style={s.emailChip}>{email}</a>
                          ))}
                        </div>
                      </div>
                    )}

                    <div style={s.contacts}>
                      {enriched.dirigeant && (
                        <ContactCard contact={enriched.dirigeant} />
                      )}
                      {enriched.rh && (
                        <ContactCard contact={enriched.rh} />
                      )}
                      {enriched.autres_contacts.map((c, j) => (
                        <ContactCard key={j} contact={c} />
                      ))}
                    </div>

                    {!enriched.emails.length && !enriched.dirigeant && !enriched.rh && enriched.autres_contacts.length === 0 && (
                      <p style={s.noContact}>Aucun contact trouvé publiquement</p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </main>
  )
}

function ContactCard({ contact }: { contact: Contact }) {
  if (!contact.nom && !contact.prenom && !contact.role) return null
  return (
    <div style={s.contactBadge}>
      {contact.role && <span style={s.contactRole}>{contact.role}</span>}
      <span style={s.contactName}>
        {[contact.prenom, contact.nom].filter(Boolean).join(' ') || '—'}
      </span>
      {contact.email && (
        <a href={`mailto:${contact.email}`} style={s.contactEmail}>{contact.email}</a>
      )}
    </div>
  )
}

const s: { [k: string]: React.CSSProperties } = {
  main: { minHeight: '100vh', padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center' },
  title: { fontSize: '2rem', marginBottom: '0.5rem' },
  desc: { color: '#666', marginBottom: '2rem', textAlign: 'center', fontSize: '0.95rem' },
  form: { width: '100%', maxWidth: '680px', backgroundColor: '#fff', padding: '2rem', borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.1)' },
  row: { display: 'flex', gap: '1rem', marginBottom: '1.5rem' },
  field: { flex: 1, display: 'flex', flexDirection: 'column', gap: '0.4rem' },
  label: { fontWeight: 600, fontSize: '0.9rem' },
  input: { padding: '0.7rem 1rem', fontSize: '1rem', border: '1px solid #ddd', borderRadius: '4px', outline: 'none' },
  btn: { width: '100%', padding: '0.75rem', fontSize: '1rem', fontWeight: 600, color: '#fff', backgroundColor: '#0070f3', border: 'none', borderRadius: '4px' },
  error: { marginTop: '1rem', padding: '1rem', backgroundColor: '#fee', color: '#c00', borderRadius: '4px', maxWidth: '680px', width: '100%' },
  results: { marginTop: '2rem', width: '100%', maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '1rem' },
  total: { color: '#555', marginBottom: '0.5rem' },
  card: { backgroundColor: '#fff', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' },
  cardHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' },
  companyName: { fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.25rem 0' },
  siteLink: { color: '#0070f3', fontSize: '0.82rem', textDecoration: 'none' },
  meta: { color: '#888', fontSize: '0.83rem', margin: '0.1rem 0' },
  enrichBtn: { flexShrink: 0, padding: '0.5rem 1rem', fontSize: '0.85rem', fontWeight: 600, color: '#0070f3', backgroundColor: '#e8f0fe', border: '1px solid #0070f3', borderRadius: '6px', cursor: 'pointer', whiteSpace: 'nowrap' },
  loadingBadge: { flexShrink: 0, padding: '0.5rem 1rem', fontSize: '0.85rem', color: '#888', backgroundColor: '#f5f5f5', borderRadius: '6px', whiteSpace: 'nowrap' },
  enrichResult: { marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #f0f0f0' },
  section: { marginBottom: '0.75rem' },
  sectionLabel: { fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase' as const, color: '#999', letterSpacing: '0.05em' },
  emailList: { display: 'flex', flexWrap: 'wrap' as const, gap: '0.4rem', marginTop: '0.4rem' },
  emailChip: { backgroundColor: '#e8f0fe', color: '#0070f3', padding: '0.25rem 0.7rem', borderRadius: '20px', fontSize: '0.85rem', textDecoration: 'none', fontFamily: 'monospace' },
  contacts: { display: 'flex', flexWrap: 'wrap' as const, gap: '0.6rem', marginTop: '0.5rem' },
  contactBadge: { border: '1px solid #eee', borderRadius: '6px', padding: '0.5rem 0.8rem', display: 'flex', flexDirection: 'column' as const, gap: '0.15rem', minWidth: '160px' },
  contactRole: { fontSize: '0.72rem', fontWeight: 700, color: '#0070f3', textTransform: 'uppercase' as const },
  contactName: { fontSize: '0.9rem', fontWeight: 600 },
  contactEmail: { fontSize: '0.78rem', color: '#555', textDecoration: 'none', fontFamily: 'monospace' },
  noContact: { color: '#bbb', fontSize: '0.85rem', fontStyle: 'italic' },
  granularityGroup: { display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' },
  granularityBtn: { flex: 1, padding: '0.6rem 0.5rem', border: '2px solid #ddd', borderRadius: '6px', backgroundColor: '#fff', cursor: 'pointer', display: 'flex', flexDirection: 'column' as const, alignItems: 'center', gap: '0.15rem' },
  granularityBtnActive: { borderColor: '#0070f3', backgroundColor: '#e8f0fe' },
  granularityLabel: { fontWeight: 600, fontSize: '0.9rem', color: '#333' },
  granularityDesc: { fontSize: '0.72rem', color: '#666' },
}
