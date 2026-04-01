import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

interface Body {
  campaignId?: string
  secteur?: string
  sous_secteur?: string
  job_title?: string
  location?: string
  targetCount?: number
}

const DEFAULT_AGENT_TARGET_COUNT = 10

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  let body: Body = {}
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  if (!body.secteur) {
    return NextResponse.json({ error: 'secteur requis' }, { status: 400 })
  }

  let campaign: { id: string; jobTitle: string; location: string } | null = null
  if (body.campaignId) {
    campaign = await prisma.campaign.findFirst({
      where: { id: body.campaignId, userId: session.user.id },
      select: { id: true, jobTitle: true, location: true },
    })
    if (!campaign) {
      return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })
    }
  }

  const resolvedJobTitle = campaign?.jobTitle ?? body.job_title?.trim()
  const resolvedLocation = campaign?.location ?? body.location?.trim()
  const resolvedTargetCount =
    typeof body.targetCount === 'number' && body.targetCount > 0
      ? Math.floor(body.targetCount)
      : DEFAULT_AGENT_TARGET_COUNT

  if (!resolvedJobTitle || !resolvedLocation) {
    return NextResponse.json({ error: 'job_title et location requis hors campagne' }, { status: 400 })
  }

  if (campaign) {
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
      return NextResponse.json({ jobId: existingJob.id })
    }
  }

  const job = await prisma.job.create({
    data: {
      userId: session.user.id,
      campaignId: campaign?.id ?? null,
      type: 'agent_search',
      status: 'pending',
      payload: {
        secteur: body.secteur,
        sousSecteur: body.sous_secteur ?? '',
        jobTitle: resolvedJobTitle,
        location: resolvedLocation,
        targetCount: resolvedTargetCount,
      },
    },
    select: { id: true },
  })

  return NextResponse.json({ jobId: job.id }, { status: 201 })
}
