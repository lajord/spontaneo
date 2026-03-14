import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

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
  const { name, jobTitle, location, radius, startDate, duration, prompt, cvData, lmText, cvFilename, enrichMode, sectors } = body

  if (!name || !jobTitle || !location) {
    return NextResponse.json({ error: 'Champs requis manquants' }, { status: 400 })
  }

  const campaign = await prisma.campaign.create({
    data: {
      userId: session.user.id,
      name,
      jobTitle,
      sectors: Array.isArray(sectors) ? sectors : [],
      location,
      radius: radius ?? 20,
      startDate: startDate ?? null,
      duration: duration ?? null,
      prompt: prompt ?? null,
      cvData: cvData ?? null,
      lmText: lmText ?? null,
      cvUrl: cvFilename ?? null,
      enrichMode: enrichMode === 'ranked' ? 'ranked' : 'basic',
    },
  })

  return NextResponse.json(campaign, { status: 201 })
}
