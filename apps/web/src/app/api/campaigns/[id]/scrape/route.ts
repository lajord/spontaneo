import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

/**
 * POST /api/campaigns/[id]/scrape
 *
 * Déclenche l'agent IA en mode "collect" :
 * - Crée un job agent_search (type, payload, mode=collect)
 * - Met campaign.status → "scraping"
 * - Retourne { jobId } — le frontend se connecte à /api/jobs/{jobId}/events pour le SSE
 */
export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id: campaignId } = await params

  const campaign = await prisma.campaign.findFirst({
    where: { id: campaignId, userId: session.user.id },
    select: {
      id: true,
      jobTitle: true,
      location: true,
      categories: true,
      sectors: true,
      granularity: true,
      status: true,
    },
  })

  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  // Vérifier qu'un job collect n'est pas déjà en cours
  const existingJob = await prisma.job.findFirst({
    where: {
      campaignId,
      userId: session.user.id,
      type: 'agent_search',
      status: { in: ['pending', 'running'] },
    },
    select: { id: true },
    orderBy: { createdAt: 'desc' },
  })

  if (existingJob) {
    return NextResponse.json({ jobId: existingJob.id })
  }

  // Déterminer le secteur depuis les categories de la campagne
  const secteur = resolveSecteur(campaign.categories, campaign.sectors)

  // Créer le job agent_search avec mode=collect
  const job = await prisma.job.create({
    data: {
      userId: session.user.id,
      campaignId,
      type: 'agent_search',
      status: 'pending',
      payload: {
        secteur,
        jobTitle: campaign.jobTitle,
        location: campaign.location,
        targetCount: 10, // Limité à 10 en dev/prod initial
        mode: 'collect',
      },
    },
    select: { id: true },
  })

  // Mettre à jour le statut de la campagne
  await prisma.campaign.update({
    where: { id: campaignId },
    data: { status: 'scraping' },
  })

  return NextResponse.json({ jobId: job.id }, { status: 201 })
}

function resolveSecteur(categories: string[], sectors: string[]): string {
  const all = [...categories, ...sectors].map(s => s.toLowerCase())

  if (all.some(s => s.includes('fond') || s.includes('investissement') || s.includes('private equity'))) {
    return 'fond_investissement'
  }
  if (all.some(s => s.includes('banque') || s.includes('bank') || s.includes('finance'))) {
    return 'banque'
  }
  // Par défaut : cabinet d'avocats
  return 'cabinet_avocat'
}
