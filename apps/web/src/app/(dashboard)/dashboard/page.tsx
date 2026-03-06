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
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Mes campagnes</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {campaigns.length} campagne{campaigns.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Link
          href="/campaigns/new"
          className="inline-flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nouvelle campagne
        </Link>
      </div>

      {/* Empty state */}
      {campaigns.length === 0 ? (
        <div className="bg-white border border-slate-100 rounded-xl py-20 text-center">
          <div className="w-12 h-12 rounded-xl bg-brand-50 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700 mb-1">Aucune campagne</p>
          <p className="text-sm text-slate-400 mb-4">Créez votre première campagne pour commencer.</p>
          <Link
            href="/campaigns/new"
            className="inline-flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Créer une campagne
          </Link>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((c) => (
            <CampaignCard key={c.id} campaign={c} />
          ))}
        </div>
      )}
    </div>
  )
}
