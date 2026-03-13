import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

export async function POST(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await prisma.campaign.findFirst({
    where: { id, userId: session.user.id },
    include: { companies: true },
  })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  let enriched = 0

  const isRanked = campaign.enrichMode === 'ranked'
  const enrichEndpoint = isRanked
    ? `${AI_SERVICE_URL}/api/v1/enrichissement/company-ranked`
    : `${AI_SERVICE_URL}/api/v1/enrichissement/company`

  // Enrichissement séquentiel pour ne pas surcharger l'API Perplexity
  for (const company of campaign.companies) {
    try {
      const res = await fetch(enrichEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nom: company.name,
          site_web: company.website ?? undefined,
          adresse: company.address ?? undefined,
          ...(isRanked ? { job_title: campaign.jobTitle } : {}),
        }),
      })

      if (!res.ok) continue

      const data = await res.json()

      // data contient : { emails: [], dirigeant: {}, rh: {}, autres_contacts: [] }
      await prisma.company.update({
        where: { id: company.id },
        data: {
          enriched: data,
          status: 'enriched',
        },
      })

      enriched++
    } catch {
      // On continue même si une entreprise échoue
    }
  }

  await prisma.campaign.update({ where: { id }, data: { status: 'enriched' } })

  return NextResponse.json({ total: campaign.companies.length, enriched })
}
