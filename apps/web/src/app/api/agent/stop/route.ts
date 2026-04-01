import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const WORKER_URL = process.env.WORKER_URL ?? 'http://localhost:3001'
const WORKER_SECRET = process.env.WORKER_SECRET ?? ''

interface Body {
  jobId?: string
  campaignId?: string
}

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  let body: Body = {}
  try {
    body = await req.json()
  } catch {}

  const job = body.jobId
    ? await prisma.job.findFirst({
        where: {
          id: body.jobId,
          userId: session.user.id,
          type: 'agent_search',
          status: { in: ['pending', 'running'] },
        },
        select: { id: true, status: true },
      })
    : await prisma.job.findFirst({
        where: {
          campaignId: body.campaignId,
          userId: session.user.id,
          type: 'agent_search',
          status: { in: ['pending', 'running'] },
        },
        select: { id: true, status: true },
        orderBy: { createdAt: 'desc' },
      })

  if (!job) {
    return NextResponse.json({ error: 'Aucun job agent actif' }, { status: 404 })
  }

  if (job.status === 'pending') {
    await prisma.job.update({
      where: { id: job.id },
      data: { status: 'cancelled', cancelRequestedAt: new Date(), completedAt: new Date() },
    })
  } else {
    await prisma.job.update({
      where: { id: job.id },
      data: { cancelRequestedAt: new Date() },
    })
    nudgeWorker()
  }

  return NextResponse.json({ ok: true, jobId: job.id })
}

function nudgeWorker(): void {
  fetch(`${WORKER_URL}/nudge`, {
    method: 'POST',
    headers: {
      ...(WORKER_SECRET ? { 'x-worker-secret': WORKER_SECRET } : {}),
    },
  }).catch(() => {})
}
