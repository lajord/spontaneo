import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { deleteCampaignFiles } from '@/lib/file-storage'

async function getCampaignOrFail(id: string, userId: string) {
  const campaign = await prisma.campaign.findFirst({ where: { id, userId } })
  return campaign
}

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await getCampaignOrFail(id, session.user.id)
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  return NextResponse.json(campaign)
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await getCampaignOrFail(id, session.user.id)
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  const body = await req.json()
  const updated = await prisma.campaign.update({ where: { id }, data: body })
  return NextResponse.json(updated)
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await getCampaignOrFail(id, session.user.id)
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  // Récupérer les IDs des emails et les autres cvUrl du même user avant suppression
  const [emails, otherCampaigns] = await Promise.all([
    prisma.email.findMany({ where: { campaignId: id }, select: { id: true } }),
    prisma.campaign.findMany({
      where: { userId: session.user.id, id: { not: id }, cvUrl: { not: null } },
      select: { cvUrl: true },
    }),
  ])

  const emailIds = emails.map(e => e.id)
  const otherCvUrls = otherCampaigns.map(c => c.cvUrl as string)

  // Supprimer en BDD (cascade supprime les emails)
  await prisma.campaign.delete({ where: { id } })

  // Nettoyer les fichiers sur disque
  await deleteCampaignFiles(session.user.id, id, campaign.cvUrl, emailIds, otherCvUrls)

  return NextResponse.json({ success: true })
}
