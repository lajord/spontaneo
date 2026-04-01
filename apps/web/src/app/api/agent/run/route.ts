import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const WORKER_URL = process.env.WORKER_URL ?? 'http://localhost:3001'
const WORKER_SECRET = process.env.WORKER_SECRET ?? ''

interface Body {
  campaignId?: string
  secteur?: string
  sous_secteur?: string
  credit_budget?: number
  dev_mode?: boolean
}

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  let body: Body = {}
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  if (!body.campaignId || !body.secteur) {
    return NextResponse.json({ error: 'campaignId et secteur requis' }, { status: 400 })
  }

  const campaign = await prisma.campaign.findFirst({
    where: { id: body.campaignId, userId: session.user.id },
    select: { id: true, jobTitle: true, location: true },
  })
  if (!campaign) {
    return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })
  }

  const existingJob = await prisma.job.findFirst({
    where: {
      userId: session.user.id,
      campaignId: campaign.id,
      type: 'agent_search',
      status: { in: ['pending', 'running'] },
    },
    select: { id: true },
    orderBy: { createdAt: 'desc' },
  })
  if (existingJob) {
    nudgeWorker()
    return NextResponse.json({ jobId: existingJob.id })
  }

  const job = await prisma.job.create({
    data: {
      userId: session.user.id,
      campaignId: campaign.id,
      type: 'agent_search',
      status: 'pending',
      payload: {
        secteur: body.secteur,
        sousSecteur: body.sous_secteur ?? '',
        jobTitle: campaign.jobTitle,
        location: campaign.location,
        creditBudget: body.credit_budget ?? null,
        devMode: body.dev_mode === true,
      },
    },
    select: { id: true },
  })

  nudgeWorker()
  return NextResponse.json({ jobId: job.id }, { status: 201 })
}

function nudgeWorker(): void {
  fetch(`${WORKER_URL}/nudge`, {
    method: 'POST',
    headers: {
      ...(WORKER_SECRET ? { 'x-worker-secret': WORKER_SECRET } : {}),
    },
  }).catch(() => {})
}
