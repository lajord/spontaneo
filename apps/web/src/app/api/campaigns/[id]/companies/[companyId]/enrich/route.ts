import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; companyId: string }> }
) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id, companyId } = await params

  // Vérifie que la campagne appartient à l'utilisateur
  const company = await prisma.company.findFirst({
    where: {
      id: companyId,
      campaign: { id, userId: session.user.id },
    },
    include: { campaign: { select: { enrichMode: true, jobTitle: true } } },
  })
  if (!company) return NextResponse.json({ error: 'Entreprise introuvable' }, { status: 404 })

  const isRanked = company.campaign.enrichMode === 'ranked'
  const enrichEndpoint = isRanked
    ? `${AI_SERVICE_URL}/api/v1/enrichissement/company-ranked`
    : `${AI_SERVICE_URL}/api/v1/enrichissement/company`

  const res = await fetch(enrichEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nom: company.name,
      site_web: company.website ?? undefined,
      adresse: company.address ?? undefined,
      ...(isRanked ? { job_title: company.campaign.jobTitle } : {}),
    }),
  })

  if (!res.ok) {
    return NextResponse.json({ error: 'Erreur service IA' }, { status: 502 })
  }

  const data = await res.json()

  const updated = await prisma.company.update({
    where: { id: companyId },
    data: { enriched: data, status: 'enriched' },
  })

  return NextResponse.json(updated)
}
