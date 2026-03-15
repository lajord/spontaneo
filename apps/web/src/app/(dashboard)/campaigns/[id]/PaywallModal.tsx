'use client'

interface PaywallModalProps {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function PaywallModal({ open, onConfirm, onCancel }: PaywallModalProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4">
          <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center mb-4">
            <svg className="w-6 h-6 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-1">Passer à l&apos;étape suivante</h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            L&apos;identification des décideurs et la rédaction personnalisée nécessitent des crédits.
            Vérifiez votre solde avant de continuer.
          </p>
        </div>

        {/* Placeholder info */}
        <div className="mx-6 mb-4 p-4 bg-slate-50 border border-slate-100 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-slate-600 font-medium">Crédits nécessaires</span>
            <span className="text-sm font-bold text-slate-900">—</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-600 font-medium">Votre solde</span>
            <span className="text-sm font-bold text-slate-900">—</span>
          </div>
        </div>

        <div className="mx-6 mb-6 p-3 bg-amber-50 border border-amber-100 rounded-lg">
          <p className="text-xs text-amber-700 font-medium text-center">
            Paywall placeholder — sera implémenté ultérieurement
          </p>
        </div>

        {/* Actions */}
        <div className="px-6 pb-6 flex items-center gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2.5 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
          >
            Continuer
          </button>
        </div>
      </div>
    </div>
  )
}
