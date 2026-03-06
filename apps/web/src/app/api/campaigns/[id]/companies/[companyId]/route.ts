import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { id: string; companyId: string } },
) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id, companyId } = params

  // Vérifie que la campagne appartient à l'utilisateur
  const campaign = await prisma.campaign.findFirst({ where: { id, userId: session.user.id } })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  const company = await prisma.company.findFirst({ where: { id: companyId, campaignId: id } })
  if (!company) return NextResponse.json({ error: 'Entreprise introuvable' }, { status: 404 })

  await prisma.company.delete({ where: { id: companyId } })

  return NextResponse.json({ success: true })
}
