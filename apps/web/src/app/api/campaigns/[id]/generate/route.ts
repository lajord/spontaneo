import { NextRequest, NextResponse } from 'next/server'
import { Prisma } from '@prisma/client'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { computeCreditsForCompanyCount, parsePositiveInteger } from '@/lib/billing/config'
import { consumeCreditsIfAvailable } from '@/lib/billing/credits'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'
const AGENT_INTERNAL_API_TOKEN = process.env.AGENT_INTERNAL_API_TOKEN ?? process.env.CRON_SECRET ?? ''

function resolveSecteur(categories: string[], sectors: string[]): string {
  const all = [...categories, ...sectors].map((s) => s.toLowerCase())

  if (all.some((s) => s.includes('fond') || s.includes('investissement') || s.includes('private equity'))) {
    return 'fond_investissement'
  }
  if (all.some((s) => s.includes('banque') || s.includes('bank') || s.includes('finance'))) {
    return 'banque'
  }
  return 'cabinet_avocat'
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) {
    return NextResponse.json({ error: 'Non autorise' }, { status: 401 })
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
    const body = await req.json()
    links = body.links ?? {}
    userMailTemplate = body.userMailTemplate ?? null
    userMailSubject = body.userMailSubject ?? null
    poolLimit = parsePositiveInteger(body.poolLimit)
    autoStart = body.autoStart === true
    dailyLimit = body.dailyLimit ?? null
    sendStartHour = body.sendStartHour ?? null
    sendEndHour = body.sendEndHour ?? null
  } catch {
    return NextResponse.json({ error: 'Payload invalide' }, { status: 400 })
  }

  if (!poolLimit) {
    return NextResponse.json({ error: "Nombre d'entreprises invalide" }, { status: 400 })
  }

  const campaign = await prisma.campaign.findFirst({
    where: { id, userId: session.user.id },
    select: { id: true, jobTitle: true, location: true, categories: true, sectors: true },
  })

  if (!campaign) {
    return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })
  }

  const secteur = resolveSecteur(campaign.categories, campaign.sectors)
  const requiredCredits = computeCreditsForCompanyCount(poolLimit)

  const transactionResult = await prisma.$transaction(async (tx) => {
    const existingJob = await tx.job.findFirst({
      where: {
        campaignId: id,
        status: { in: ['pending', 'running'] },
        OR: [
          { type: 'campaign_generate' },
          { type: 'agent_search', payload: { path: ['mode'], equals: 'enrich' } },
        ],
      },
      select: { id: true, payload: true },
      orderBy: { createdAt: 'desc' },
    })

    if (existingJob) {
      const payload = (existingJob.payload as any) || {}
      return {
        kind: 'existing' as const,
        jobId: existingJob.id,
        poolLimit: payload.poolLimit ?? payload.generateConfig?.poolLimit ?? poolLimit,
      }
    }

    const consumed = await consumeCreditsIfAvailable(tx, session.user.id, requiredCredits)

    if (!consumed) {
      const user = await tx.user.findUnique({
        where: { id: session.user.id },
        select: { credits: true },
      })

      return {
        kind: 'insufficient' as const,
        currentCredits: user?.credits ?? 0,
      }
    }

    if (autoStart) {
      await tx.campaign.update({
        where: { id },
        data: {
          autoStart: true,
          ...(dailyLimit !== null && { dailyLimit }),
          ...(sendStartHour !== null && { sendStartHour }),
          ...(sendEndHour !== null && { sendEndHour }),
        },
      })
    }

    const job = await tx.job.create({
      data: {
        userId: session.user.id,
        campaignId: id,
        type: 'agent_search',
        status: 'pending',
        payload: {
          secteur,
          jobTitle: campaign.jobTitle,
          location: campaign.location,
          mode: 'enrich',
          generateConfig: { links, userMailTemplate, userMailSubject, poolLimit, autoStart, requiredCredits },
        },
      },
      select: { id: true },
    })

    await tx.campaign.update({
      where: { id },
      data: { status: 'enriching' },
    })

    return {
      kind: 'created' as const,
      jobId: job.id,
    }
  }, {
    isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
  })

  if (transactionResult.kind === 'existing') {
    return NextResponse.json({ jobId: transactionResult.jobId, poolLimit: transactionResult.poolLimit })
  }

  if (transactionResult.kind === 'insufficient') {
    return NextResponse.json(
      {
        error: 'Credits insuffisants',
        currentCredits: transactionResult.currentCredits,
        requiredCredits,
        missingCredits: Math.max(requiredCredits - transactionResult.currentCredits, 0),
      },
      { status: 402 },
    )
  }

  nudgeAiService(transactionResult.jobId, {
    secteur,
    job_title: campaign.jobTitle,
    location: campaign.location,
    mode: 'enrich',
    job_id: transactionResult.jobId,
    campaign_id: id,
    user_id: session.user.id,
  }).catch(() => {
    // Le worker reprendra ce job au cycle suivant.
  })

  return NextResponse.json({ jobId: transactionResult.jobId })
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
