import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const WORKER_URL = process.env.WORKER_URL ?? 'http://localhost:3001'
const WORKER_SECRET = process.env.WORKER_SECRET ?? ''

export async function POST(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) {
    return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  }

  const { id } = await params

  let links: { linkedin?: string; github?: string; portfolio?: string; custom?: { label: string; url: string }[] } = {}
  let userMailTemplate: string | null = null
  let userMailSubject: string | null = null
  try {
    const body = await _req.json()
    links = body.links ?? {}
    userMailTemplate = body.userMailTemplate ?? null
    userMailSubject = body.userMailSubject ?? null
  } catch { /* body vide ou absent */ }

  const campaign = await prisma.campaign.findFirst({
    where: { id, userId: session.user.id },
    select: { id: true, status: true },
  })

  if (!campaign) {
    return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })
  }

  // ── Si un job est déjà en cours pour cette campagne, retourner son ID ──────
  const existingJob = await prisma.job.findFirst({
    where: {
      campaignId: id,
      status: { in: ['pending', 'running'] },
    },
    select: { id: true },
    orderBy: { createdAt: 'desc' },
  })

  if (existingJob) {
    return NextResponse.json({ jobId: existingJob.id })
  }

  // ── Créer un nouveau Job en DB ─────────────────────────────────────────────
  const job = await prisma.job.create({
    data: {
      userId: session.user.id,
      campaignId: id,
      status: 'pending',
      payload: { links, userMailTemplate, userMailSubject },
    },
  })

  // ── Notifier le worker via HTTP ───────────────────────────────────────────
  fetch(`${WORKER_URL}/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(WORKER_SECRET ? { 'x-worker-secret': WORKER_SECRET } : {}),
    },
    body: JSON.stringify({
      jobId: job.id,
      campaignId: id,
      links,
      userMailTemplate,
      userMailSubject,
    }),
  }).catch(err => console.error('[generate] Worker notification failed:', err))

  return NextResponse.json({ jobId: job.id })
}
