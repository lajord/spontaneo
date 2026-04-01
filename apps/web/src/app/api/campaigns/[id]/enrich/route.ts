import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'
const AGENT_INTERNAL_API_TOKEN = process.env.AGENT_INTERNAL_API_TOKEN ?? process.env.CRON_SECRET ?? ''

/**
 * POST /api/campaigns/[id]/enrich
 *
 * Déclenche l'agent IA en mode "enrich" sur les AgentCandidate (status=pending)
 * issus du job de collecte.
 * - Crée un job agent_enrich
 * - Met campaign.status → "enriching"
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
      status: true,
    },
  })

  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  // Récupérer le job de collecte associé (pour passer son ID à l'agent enrich)
  const collectJob = await prisma.job.findFirst({
    where: {
      campaignId,
      userId: session.user.id,
      type: 'agent_search',
      status: 'completed',
    },
    select: { id: true, payload: true },
    orderBy: { createdAt: 'desc' },
  })

  if (!collectJob) {
    return NextResponse.json(
      { error: 'Aucun job de collecte terminé trouvé pour cette campagne' },
      { status: 400 },
    )
  }

  // Vérifier qu'un job enrich n'est pas déjà en cours
  const existingEnrichJob = await prisma.job.findFirst({
    where: {
      campaignId,
      userId: session.user.id,
      type: 'agent_enrich',
      status: { in: ['pending', 'running'] },
    },
    select: { id: true },
  })

  if (existingEnrichJob) {
    return NextResponse.json({ jobId: existingEnrichJob.id })
  }

  const secteur = resolveSecteur(campaign.categories, campaign.sectors)
  const collectPayload = (collectJob.payload as Record<string, unknown>) ?? {}

  // Créer le job agent_enrich
  const enrichJob = await prisma.job.create({
    data: {
      userId: session.user.id,
      campaignId,
      type: 'agent_enrich',
      status: 'pending',
      payload: {
        secteur,
        jobTitle: campaign.jobTitle,
        location: campaign.location,
        mode: 'enrich',
        collectJobId: collectJob.id,
        // Transmettre le contact_brief stocké dans le job collect
        contact_brief: (collectPayload as any).contact_brief ?? '',
      },
    },
    select: { id: true },
  })

  // Mettre à jour le statut de la campagne
  await prisma.campaign.update({
    where: { id: campaignId },
    data: { status: 'enriching' },
  })

  // Notifier le FastAPI AI-service pour qu'il démarre le job enrich
  nudgeAiService(enrichJob.id, {
    secteur,
    job_title: campaign.jobTitle,
    location: campaign.location,
    mode: 'enrich',
    job_id: enrichJob.id,
    collect_job_id: collectJob.id,
    campaign_id: campaignId,
    user_id: session.user.id,
  }).catch(() => {})

  return NextResponse.json({ jobId: enrichJob.id }, { status: 201 })
}

function resolveSecteur(categories: string[], sectors: string[]): string {
  const all = [...categories, ...sectors].map(s => s.toLowerCase())
  if (all.some(s => s.includes('fond') || s.includes('investissement') || s.includes('private equity'))) {
    return 'fond_investissement'
  }
  if (all.some(s => s.includes('banque') || s.includes('bank') || s.includes('finance'))) {
    return 'banque'
  }
  return 'cabinet_avocat'
}

async function nudgeAiService(jobId: string, body: Record<string, unknown>): Promise<void> {
  await fetch(`${AI_SERVICE_URL}/api/v1/agent/run-job`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(AGENT_INTERNAL_API_TOKEN ? { Authorization: `Bearer ${AGENT_INTERNAL_API_TOKEN}` } : {}),
    },
    body: JSON.stringify({ jobId, ...body }),
    signal: AbortSignal.timeout(5000),
  })
}
