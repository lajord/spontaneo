import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function GET(req: NextRequest) {
  // Vérification du secret cron (désactivé en dev pour faciliter les tests locaux)
  if (process.env.NODE_ENV !== 'development') {
    const authHeader = req.headers.get('authorization')
    const cronSecret = process.env.CRON_SECRET
    if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
      return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
    }
  }

  console.log(`[cron] 🧹 Début du nettoyage des ContactedCompany vieux de plus de 30 jours...`)

  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  try {
    const { count } = await (prisma as any).contactedCompany.deleteMany({
      where: {
        contactedAt: {
          lt: thirtyDaysAgo,
        },
      },
    })

    console.log(`[cron] 🧹 Nettoyage terminé. ${count} entreprise(s) supprimée(s).`)
    return NextResponse.json({ deletedCount: count, timestamp: new Date().toISOString() })
  } catch (error) {
    console.error(`[cron] ❌ Erreur lors du nettoyage des contacts :`, error)
    return NextResponse.json({ error: 'Failed to clean up contacted companies' }, { status: 500 })
  }
}
