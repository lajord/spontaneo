import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { deleteCampaignFiles } from '@/lib/file-storage'

export async function DELETE() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const userId = session.user.id

  // Récupérer toutes les campagnes avec leurs emails pour le nettoyage fichiers
  const campaigns = await prisma.campaign.findMany({
    where: { userId },
    select: {
      id: true,
      cvUrl: true,
      emails: { select: { id: true } },
    },
  })

  // Supprimer le compte (cascade BDD sur tout le reste)
  await prisma.user.delete({ where: { id: userId } })

  // Nettoyer les fichiers sur disque après la suppression BDD
  for (const campaign of campaigns) {
    await deleteCampaignFiles(
      userId,
      campaign.id,
      campaign.cvUrl,
      campaign.emails.map(e => e.id),
      [],
    )
  }

  return NextResponse.json({ success: true })
}
