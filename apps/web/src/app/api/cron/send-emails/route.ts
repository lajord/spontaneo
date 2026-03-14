import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { sendEmail, Attachment, OAuthExpiredError } from '@/lib/email-sender'
import { readCvFile, readLmFile } from '@/lib/file-storage'

export async function GET(req: NextRequest) {
  // Vérification du secret cron (désactivé en dev pour faciliter les tests locaux)
  if (process.env.NODE_ENV !== 'development') {
    const authHeader = req.headers.get('authorization')
    const cronSecret = process.env.CRON_SECRET
    if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
      return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
    }
  }

  // Heure actuelle en timezone Paris
  const nowParis = new Date(new Date().toLocaleString('en-US', { timeZone: 'Europe/Paris' }))
  const currentHour = nowParis.getHours()

  // Minuit aujourd'hui en Paris (pour le comptage journalier)
  const midnightParis = new Date(nowParis)
  midnightParis.setHours(0, 0, 0, 0)

  const dayOfWeek = nowParis.getDay() // 0 = dimanche, 6 = samedi
  console.log(`[cron] ⏰ Heure Paris : ${currentHour}h | jour: ${dayOfWeek}`)

  if (dayOfWeek === 0 || dayOfWeek === 6) {
    console.log(`[cron] 🚫 Weekend détecté — aucun envoi`)
    return NextResponse.json({ processed: 0, skipped: 0, skipReasons: ['Weekend — aucun envoi'], timestamp: new Date().toISOString() })
  }

  const activeCampaigns = await prisma.campaign.findMany({
    where: { status: 'active' },
  })

  console.log(`[cron] 📋 ${activeCampaigns.length} campagne(s) active(s) trouvée(s)`)

  if (activeCampaigns.length === 0) {
    const allCampaigns = await prisma.campaign.findMany({ select: { id: true, name: true, status: true } })
    console.log(`[cron] ℹ️ Toutes les campagnes :`, JSON.stringify(allCampaigns))
  }

  let processed = 0
  let skipped = 0
  const skipReasons: string[] = []

  for (const campaign of activeCampaigns) {
    const startHour = campaign.sendStartHour ?? 8
    const endHour = campaign.sendEndHour ?? 18
    const dailyLimit = campaign.dailyLimit ?? 50
    const totalEmails = campaign.totalEmails ?? 0

    console.log(`[cron] 🏢 Campagne "${campaign.name}" — fenêtre ${startHour}h-${endHour}h | limite/jour: ${dailyLimit} | total: ${totalEmails} | envoyés: ${campaign.sentCount}`)

    // 1. Vérifier fenêtre horaire
    if (currentHour < startHour || currentHour >= endHour) {
      const reason = `"${campaign.name}" skippée → heure actuelle ${currentHour}h hors fenêtre [${startHour}h-${endHour}h]`
      console.log(`[cron] ⏩ ${reason}`)
      skipReasons.push(reason)
      skipped++
      continue
    }

    // 2. Vérifier la limite journalière
    const sentToday = await prisma.email.count({
      where: {
        campaignId: campaign.id,
        status: 'sent',
        sentAt: { gte: midnightParis },
      },
    })
    console.log(`[cron] 📊 Envoyés aujourd'hui : ${sentToday} / ${dailyLimit}`)
    if (sentToday >= dailyLimit) {
      const reason = `"${campaign.name}" skippée → limite journalière atteinte (${sentToday}/${dailyLimit})`
      console.log(`[cron] ⏩ ${reason}`)
      skipReasons.push(reason)
      skipped++
      continue
    }

    // 3. Vérifier l'intervalle depuis le dernier envoi
    const intervalMinutes = Math.floor(1440 / dailyLimit)
    const lastSent = await prisma.email.findFirst({
      where: { campaignId: campaign.id, status: 'sent' },
      orderBy: { sentAt: 'desc' },
    })
    if (lastSent?.sentAt) {
      const minutesSinceLast = (Date.now() - lastSent.sentAt.getTime()) / 60000
      console.log(`[cron] ⏱️ Dernier envoi il y a ${minutesSinceLast.toFixed(1)} min | intervalle requis: ${intervalMinutes} min`)
      if (minutesSinceLast < intervalMinutes) {
        const reason = `"${campaign.name}" skippée → intervalle pas respecté (${minutesSinceLast.toFixed(1)} min < ${intervalMinutes} min requis)`
        console.log(`[cron] ⏩ ${reason}`)
        skipReasons.push(reason)
        skipped++
        continue
      }
    } else {
      console.log(`[cron] ✅ Aucun envoi précédent — pas d'intervalle à respecter`)
    }

    // 4. Vérifier le compteur total
    if (totalEmails > 0 && campaign.sentCount >= totalEmails) {
      const reason = `"${campaign.name}" skippée → quota total atteint (${campaign.sentCount}/${totalEmails}) → marquée finished`
      console.log(`[cron] ⏩ ${reason}`)
      skipReasons.push(reason)
      await prisma.campaign.update({ where: { id: campaign.id }, data: { status: 'finished' } })
      skipped++
      continue
    }

    // 5. Prendre le prochain email draft
    const nextEmail = await prisma.email.findFirst({
      where: { campaignId: campaign.id, status: 'draft' },
      include: { company: true },
      orderBy: { createdAt: 'asc' },
    })
    if (!nextEmail) {
      const reason = `"${campaign.name}" skippée → aucun email en statut 'draft' → marquée finished`
      console.log(`[cron] ⏩ ${reason}`)
      skipReasons.push(reason)
      await prisma.campaign.update({ where: { id: campaign.id }, data: { status: 'finished' } })
      skipped++
      continue
    }
    console.log(`[cron] 📧 Prochain email : id=${nextEmail.id} | to=${nextEmail.to} | entreprise="${nextEmail.company.name}"`)

    // 6. Récupérer la config email de l'utilisateur
    const config = await prisma.emailConfig.findUnique({ where: { userId: campaign.userId } })
    if (!config?.accessToken) {
      const reason = `"${campaign.name}" skippée → pas de config email OAuth pour userId=${campaign.userId}`
      console.log(`[cron] ⏩ ${reason}`)
      skipReasons.push(reason)
      skipped++
      continue
    }
    console.log(`[cron] ✅ Config email trouvée — provider: ${config.provider} | oauthEmail: ${config.oauthEmail}`)

    // 7. Envoyer
    const toEmail =
      nextEmail.to ??
      (nextEmail.company.enriched as { emails?: string[] } | null)?.emails?.[0] ??
      null

    if (!toEmail) {
      const reason = `"${campaign.name}" — email ${nextEmail.id} sans destinataire → marqué failed`
      console.log(`[cron] ⚠️ ${reason}`)
      skipReasons.push(reason)
      await prisma.email.update({
        where: { id: nextEmail.id },
        data: { status: 'failed' },
      })
      skipped++
      continue
    }

    // ── Pièces jointes ──────────────────────────────────────────────────────
    const attachments: Attachment[] = []

    if (campaign.cvUrl) {
      const cvBuffer = await readCvFile(campaign.userId, campaign.cvUrl)
      if (cvBuffer) {
        attachments.push({ name: 'CV.pdf', content: cvBuffer, contentType: 'application/pdf' })
      }
    }

    const lmBuffer = await readLmFile(campaign.userId, nextEmail.id)
    if (lmBuffer) {
      attachments.push({
        name: 'Lettre_de_motivation.docx',
        content: lmBuffer,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
    }

    console.log(`[cron] 🚀 Envoi vers ${toEmail} avec ${attachments.length} pièce(s) jointe(s)...`)

    try {
      await sendEmail(config, { to: toEmail, subject: nextEmail.subject, body: nextEmail.body, attachments })
      const newSentCount = campaign.sentCount + 1
      await prisma.$transaction([
        prisma.email.update({
          where: { id: nextEmail.id },
          data: { status: 'sent', sentAt: new Date() },
        }),
        prisma.campaign.update({
          where: { id: campaign.id },
          data: {
            sentCount: newSentCount,
            ...(totalEmails > 0 && newSentCount >= totalEmails ? { status: 'finished' } : {}),
          },
        }),
      ])
      console.log(`[cron] ✅ Email envoyé avec succès ! sentCount=${newSentCount}`)
      processed++
    } catch (err) {
      if (err instanceof OAuthExpiredError) {
        const reason = `"${campaign.name}" — token OAuth expiré/révoqué : l'utilisateur doit reconnecter son compte email depuis les Paramètres`
        console.error(`[cron] 🔒 ${reason}`)
        skipReasons.push(reason)
      } else {
        console.error(`[cron] ❌ Erreur envoi email ${nextEmail.id}:`, err)
      }
      skipped++
    }
  }

  console.log(`[cron] 🏁 Terminé — processed: ${processed} | skipped: ${skipped}`)
  if (skipReasons.length > 0) {
    console.log(`[cron] 📋 Raisons des skips :`, skipReasons)
  }

  return NextResponse.json({ processed, skipped, skipReasons, timestamp: new Date().toISOString() })
}
