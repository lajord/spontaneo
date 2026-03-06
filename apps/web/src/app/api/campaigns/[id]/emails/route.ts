import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await prisma.campaign.findFirst({ where: { id, userId: session.user.id } })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  const emails = await prisma.email.findMany({
    where: { campaignId: id },
    include: { company: true },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json(emails)
}

// Générer les mails pour toutes les entreprises d'une campagne
export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await prisma.campaign.findFirst({
    where: { id, userId: session.user.id },
    include: { companies: true },
  })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  const body = await req.json().catch(() => ({}))
  const companyIds: string[] = body.companyIds ?? campaign.companies.map((c) => c.id)

  const companies = campaign.companies.filter((c) => companyIds.includes(c.id))

  // Appel service IA pour génération des mails
  const response = await fetch(`${AI_SERVICE_URL}/api/v1/generation/emails`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      campaign: {
        jobTitle: campaign.jobTitle,
        prompt: campaign.prompt,
        cvUrl: campaign.cvUrl,
      },
      companies: companies.map((c) => ({
        id: c.id,
        name: c.name,
        website: c.website,
        address: c.address,
      })),
    }),
  })

  if (!response.ok) {
    return NextResponse.json({ error: 'Erreur génération IA' }, { status: 502 })
  }

  const generated: Array<{ companyId: string; subject: string; body: string }> =
    await response.json()

  const created = await prisma.$transaction(
    generated.map((g) =>
      prisma.email.create({
        data: {
          campaignId: id,
          companyId: g.companyId,
          subject: g.subject,
          body: g.body,
          status: 'draft',
        },
      })
    )
  )

  return NextResponse.json({ total: created.length, emails: created })
}
