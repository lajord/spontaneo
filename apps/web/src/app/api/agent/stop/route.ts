import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { appendJobEvent } from '@/lib/job-events'

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
          userId: session.user.id,
          type: 'agent_search',
          status: { in: ['pending', 'running'] },
          ...(body.campaignId ? { campaignId: body.campaignId } : {}),
        },
        select: { id: true, status: true },
        orderBy: { createdAt: 'desc' },
      })

  if (!job) {
    return NextResponse.json({ error: 'Aucun job agent actif' }, { status: 404 })
  }

  if (job.status === 'pending') {
    await prisma.$transaction(async (tx) => {
      await tx.job.update({
        where: { id: job.id },
        data: { status: 'cancelled', cancelRequestedAt: new Date(), completedAt: new Date() },
      })
      await appendJobEvent(tx, job.id, {
        type: 'cancelled',
        message: 'Job agent annule avant demarrage',
      })
    })
  } else {
    await prisma.job.update({
      where: { id: job.id },
      data: { cancelRequestedAt: new Date() },
    })
  }

  return NextResponse.json({ ok: true, jobId: job.id })
}
