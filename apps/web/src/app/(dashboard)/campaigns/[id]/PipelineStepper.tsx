'use client'

type StepStatus = 'pending' | 'active' | 'completed'

interface PipelineStepperProps {
  stepStatuses: Record<number, StepStatus>
  campaignStatus: string
}

const PIPELINE_STEPS = [
  {
    num: 1,
    label: 'Scraping entreprises',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
      </svg>
    ),
  },
  {
    num: 2,
    label: 'Identification décideurs',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    ),
  },
  {
    num: 3,
    label: 'Rédaction personnalisée',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    num: 4,
    label: 'Prêt pour envoi',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
]

function statusBadge(campaignStatus: string) {
  switch (campaignStatus) {
    case 'draft':
      return { label: 'En attente', className: 'text-amber-700 bg-amber-50 border-amber-200' }
    case 'scraping':
      return { label: 'Collecte en cours', className: 'text-sky-700 bg-sky-50 border-sky-200' }
    case 'scraped':
      return { label: 'Collecte terminée', className: 'text-brand-700 bg-brand-50 border-brand-200' }
    case 'generating':
      return { label: 'En cours', className: 'text-indigo-700 bg-indigo-50 border-indigo-200' }
    case 'active':
      return { label: 'Active', className: 'text-emerald-700 bg-emerald-50 border-emerald-200' }
    case 'paused':
      return { label: 'En pause', className: 'text-amber-700 bg-amber-50 border-amber-200' }
    case 'finished':
      return { label: 'Terminée', className: 'text-slate-600 bg-slate-100 border-slate-300' }
    default:
      return { label: 'En attente', className: 'text-amber-700 bg-amber-50 border-amber-200' }
  }
}

export default function PipelineStepper({ stepStatuses, campaignStatus }: PipelineStepperProps) {
  const badge = statusBadge(campaignStatus)

  return (
    <div className="border border-slate-300 rounded-2xl p-6 bg-white">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-bold text-slate-900">Pipeline</h2>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${badge.className}`}>
          {badge.label}
        </span>
      </div>

      <div className="flex items-center w-full">
        {PIPELINE_STEPS.map((step, i) => {
          const status = stepStatuses[step.num] ?? 'pending'
          return (
            <div key={step.num} className="flex items-center flex-1 last:flex-none">
              <div className="flex items-center gap-2.5 shrink-0">
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-300 ${
                    status === 'completed'
                      ? 'bg-emerald-500 text-white shadow-sm shadow-emerald-500/20'
                      : status === 'active'
                        ? 'bg-slate-900 text-white shadow-sm shadow-slate-900/20 ring-[3px] ring-slate-900/10'
                        : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {status === 'completed' ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    step.icon
                  )}
                </div>
                <span
                  className={`text-[13px] font-medium whitespace-nowrap transition-colors duration-300 ${
                    status === 'active'
                      ? 'text-slate-900'
                      : status === 'completed'
                        ? 'text-emerald-600'
                        : 'text-slate-600'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <div
                  className={`flex-1 mx-4 h-[2px] transition-colors duration-500 ${
                    status === 'completed' ? 'bg-emerald-300' : 'bg-slate-200'
                  }`}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
