import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = await params
  const { dailyLimit, sendStartHour, sendEndHour } = await req.json() as {
    dailyLimit: number
    sendStartHour: number
    sendEndHour: number
  }

  if (!dailyLimit || dailyLimit < 1 || dailyLimit > 500) {
    return NextResponse.json({ error: 'dailyLimit invalide (1-500)' }, { status: 400 })
  }
  if (sendStartHour < 0 || sendStartHour > 23 || sendEndHour < 1 || sendEndHour > 24 || sendStartHour >= sendEndHour) {
    return NextResponse.json({ error: 'Fenêtre horaire invalide' }, { status: 400 })
  }

  const campaign = await prisma.campaign.findFirst({ where: { id, userId: session.user.id } })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  const config = await prisma.emailConfig.findUnique({ where: { userId: session.user.id } })
  if (!config?.accessToken) {
    return NextResponse.json({ error: 'Aucune boîte mail connectée' }, { status: 400 })
  }

  // S'il y a un job d'enrichissement en cours, on permet quand même l'enregistrement
  // mais on n'exige pas d'avoir des brouillons tout de suite.
  const runningJob = await prisma.job.findFirst({
    where: { campaignId: id, status: { in: ['pending', 'running'] } }
  })

  // Snapshot du nombre de mails à envoyer au moment du lancement (si pas de job en cours)
  const totalEmails = await prisma.email.count({ where: { campaignId: id, status: 'draft' } })
  if (!runningJob && totalEmails === 0) {
    return NextResponse.json({ error: 'Aucun mail en attente d\'envoi' }, { status: 400 })
  }

  if (runningJob) {
    // On met à jour le Job pour qu'il lance la campagne automatiquement à la fin
    const payload = (runningJob.payload as any) || {}
    payload.autoStart = true

    await prisma.job.update({
      where: { id: runningJob.id },
      data: { payload }
    })

    // On pré-enregistre les paramètres de la campagne
    await prisma.campaign.update({
      where: { id },
      data: {
        dailyLimit,
        sendStartHour,
        sendEndHour,
      },
    })

    return NextResponse.json({ activated: true, pendingGeneration: true })
  }

  await prisma.campaign.update({
    where: { id },
    data: {
      status: 'active',
      dailyLimit,
      sendStartHour,
      sendEndHour,
      totalEmails,
      sentCount: 0,
      launchedAt: new Date(),
    },
  })

  return NextResponse.json({ activated: true, totalEmails })
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = await params

  const campaign = await prisma.campaign.findFirst({ where: { id, userId: session.user.id } })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  await prisma.campaign.update({
    where: { id },
    data: { status: 'paused' },
  })

  return NextResponse.json({ paused: true })
}
