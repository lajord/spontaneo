import { NextRequest, NextResponse } from 'next/server'
import { Prisma } from '@prisma/client'
import { prisma } from '@/lib/prisma'
import { authorizeAgentRoute } from '@/lib/agent-auth'

/**
 * GET  /api/agent/job/[jobId]/payload  — lit le payload JSON du job
 * PATCH /api/agent/job/[jobId]/payload  — merge des champs dans le payload
 *
 * Utilisé par graph.py pour persister/lire le contact_brief entre les phases
 * collect et enrich du pipeline agent.
 */

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  const { jobId } = await params

  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { payload: true },
  })

  if (!job) return NextResponse.json({ error: 'Job introuvable' }, { status: 404 })

  return NextResponse.json((job.payload as Record<string, unknown>) ?? {})
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  const { jobId } = await params

  let body: Record<string, unknown> = {}
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps invalide' }, { status: 400 })
  }

  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { id: true, payload: true },
  })

  if (!job) return NextResponse.json({ error: 'Job introuvable' }, { status: 404 })

  const existing = (job.payload as Record<string, unknown>) ?? {}
  const merged = { ...existing, ...body }

  await prisma.job.update({
    where: { id: jobId },
    data: { payload: merged },
  })

  return NextResponse.json({ ok: true })
}
