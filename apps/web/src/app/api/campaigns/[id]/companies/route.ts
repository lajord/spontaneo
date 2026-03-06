import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await prisma.campaign.findFirst({ where: { id, userId: session.user.id } })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  const companies = await prisma.company.findMany({
    where: { campaignId: id },
    include: { _count: { select: { emails: true } } },
    orderBy: { scrapedAt: 'desc' },
  })

  return NextResponse.json(companies)
}
