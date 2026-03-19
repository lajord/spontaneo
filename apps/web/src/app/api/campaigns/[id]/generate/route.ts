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
  let poolLimit: number | null = null
  let autoStart = false
  let dailyLimit: number | null = null
  let sendStartHour: number | null = null
  let sendEndHour: number | null = null
  try {
    const body = await _req.json()
    links = body.links ?? {}
    userMailTemplate = body.userMailTemplate ?? null
    userMailSubject = body.userMailSubject ?? null
    poolLimit = body.poolLimit ?? null
    autoStart = body.autoStart === true
    dailyLimit = body.dailyLimit ?? null
    sendStartHour = body.sendStartHour ?? null
    sendEndHour = body.sendEndHour ?? null
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
    select: { id: true, payload: true },
    orderBy: { createdAt: 'desc' },
  })

  if (existingJob) {
    nudgeWorker()
    const payload = (existingJob.payload as any) || {}
    return NextResponse.json({ jobId: existingJob.id, poolLimit: payload.poolLimit })
  }

  // ── Persister autoStart + send settings sur la campagne ──────────────────
  if (autoStart) {
    await prisma.campaign.update({
      where: { id },
      data: {
        autoStart: true,
        ...(dailyLimit !== null && { dailyLimit }),
        ...(sendStartHour !== null && { sendStartHour }),
        ...(sendEndHour !== null && { sendEndHour }),
      },
    })
  }

  // ── Créer un nouveau Job en DB — le worker le découvrira via polling ───────
  const job = await prisma.job.create({
    data: {
      userId: session.user.id,
      campaignId: id,
      status: 'pending',
      payload: { links, userMailTemplate, userMailSubject, poolLimit, autoStart },
    },
  })

  nudgeWorker()

  return NextResponse.json({ jobId: job.id })
}

function nudgeWorker(): void {
  fetch(`${WORKER_URL}/nudge`, {
    method: 'POST',
    headers: {
      ...(WORKER_SECRET ? { 'x-worker-secret': WORKER_SECRET } : {}),
    },
  }).catch(() => {
    // Worker down — pas grave, il trouvera le job au prochain poll
  })
}
