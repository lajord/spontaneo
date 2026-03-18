export const dynamic = 'force-dynamic'

import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import Link from 'next/link'
import CampaignCard from './CampaignCard'

export default async function DashboardPage() {
  const session = await auth.api.getSession({ headers: headers() })
  const campaigns = await prisma.campaign.findMany({
    where: { userId: session!.user.id },
    include: { _count: { select: { companies: true, emails: true } } },
    orderBy: { createdAt: 'desc' },
  })

  return (
    <div className="p-8 max-w-7xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-200/60">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Mes campagnes</h1>
          <p className="text-sm text-slate-500 mt-1">
            Gérez vos recherches d'opportunités et suivez vos candidatures.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-sm font-medium text-slate-500 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm">
            Total: <span className="text-slate-900">{campaigns.length}</span>
          </div>
          <Link
            href="/campaigns/new"
            className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-all shadow-sm shadow-brand-500/20"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
            </svg>
            Nouvelle campagne
          </Link>
        </div>
      </div>

      {/* Empty state */}
      {campaigns.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center shadow-sm max-w-2xl mx-auto mt-12">
          <div className="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-5 border border-brand-100">
            <svg className="w-8 h-8 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-2">Aucune campagne active</h3>
          <p className="text-slate-500 mb-8 max-w-md mx-auto">
            Créez votre première campagne pour rechercher des entreprises et générer des candidatures spontanées.
          </p>
          <Link
            href="/campaigns/new"
            className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-all shadow-sm"
          >
            Créer ma première campagne
          </Link>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((c) => (
            <CampaignCard key={c.id} campaign={c} />
          ))}
        </div>
      )}
    </div>
  )
}
