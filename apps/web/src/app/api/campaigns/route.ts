import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

function resolveAgentSecteur(categories: string[], sectors: string[]): string {
  const all = [...categories, ...sectors].map((value) => value.toLowerCase())

  if (all.some((value) => value.includes('fond') || value.includes('investissement') || value.includes('private equity'))) {
    return 'fond_investissement'
  }
  if (all.some((value) => value.includes('banque') || value.includes('bank') || value.includes('finance'))) {
    return 'banque'
  }

  return 'cabinet_avocat'
}

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const campaigns = await prisma.campaign.findMany({
    where: { userId: session.user.id },
    include: { _count: { select: { companies: true, emails: true } } },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json(campaigns)
}

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const body = await req.json()
  const { name, jobTitle, location, radius, startDate, duration, prompt, cvData, lmText, cvFilename, enrichMode, sectors, categories } = body

  if (!name || !jobTitle || !location) {
    return NextResponse.json({ error: 'Champs requis manquants' }, { status: 400 })
  }

  const normalizedSectors = Array.isArray(sectors) ? sectors : []
  const normalizedCategories = Array.isArray(categories) ? categories : []
  const secteur = resolveAgentSecteur(normalizedCategories, normalizedSectors)

  const result = await prisma.$transaction(async (tx) => {
    const campaign = await tx.campaign.create({
      data: {
        userId: session.user.id,
        name,
        jobTitle,
        sectors: normalizedSectors,
        categories: normalizedCategories,
        location,
        radius: radius ?? 20,
        startDate: startDate ?? null,
        duration: duration ?? null,
        prompt: prompt ?? null,
        cvData: cvData ?? null,
        lmText: lmText ?? null,
        cvUrl: cvFilename ?? null,
        enrichMode: enrichMode === 'ranked' ? 'ranked' : 'basic',
        status: 'scraping',
      },
    })

    const agentJob = await tx.job.create({
      data: {
        userId: session.user.id,
        campaignId: campaign.id,
        type: 'agent_search',
        status: 'pending',
        payload: {
          secteur,
          jobTitle,
          location,
          targetCount: 10,
          mode: 'collect',
        },
      },
      select: { id: true },
    })

    return { ...campaign, agentJobId: agentJob.id }
  })

  return NextResponse.json(result, { status: 201 })
}
