import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { sendEmail, Attachment } from '@/lib/email-sender'
import { readCvFile, readLmFile } from '@/lib/file-storage'

export async function POST(_req: NextRequest, { params }: { params: Promise<{ emailId: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { emailId } = await params

  const email = await prisma.email.findFirst({
    where: { id: emailId, campaign: { userId: session.user.id } },
    include: { company: true, campaign: true },
  })
  if (!email) return NextResponse.json({ error: 'Email introuvable' }, { status: 404 })

  const config = await prisma.emailConfig.findUnique({ where: { userId: session.user.id } })
  if (!config?.accessToken) {
    return NextResponse.json(
      { error: 'Aucune boîte mail connectée. Connectez Gmail ou Outlook dans les Paramètres.' },
      { status: 400 }
    )
  }

  const toEmail =
    email.to ??
    (email.company.enriched as { emails?: string[] } | null)?.emails?.[0] ??
    null

  if (!toEmail) {
    return NextResponse.json({ error: "Pas d'adresse email pour ce destinataire" }, { status: 400 })
  }

  // ── Pièces jointes ────────────────────────────────────────────────────────
  const attachments: Attachment[] = []

  // CV : stocké sous uploads/piece_jointe/{userId}/cv/{cvUrl}
  if (email.campaign.cvUrl) {
    const cvBuffer = await readCvFile(session.user.id, email.campaign.cvUrl)
    if (cvBuffer) {
      attachments.push({ name: 'CV.pdf', content: cvBuffer, contentType: 'application/pdf' })
    } else {
      console.warn(`[SEND] CV introuvable pour campagne ${email.campaign.id}: ${email.campaign.cvUrl}`)
    }
  }

  // LM personnalisée : stockée sous uploads/piece_jointe/{userId}/lm/{emailId}.docx
  const lmBuffer = await readLmFile(session.user.id, email.id)
  if (lmBuffer) {
    attachments.push({
      name: 'Lettre_de_motivation.docx',
      content: lmBuffer,
      contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
  }

  try {
    await sendEmail(config, { to: toEmail, subject: email.subject, body: email.body, attachments })
  } catch (err) {
    const message = err instanceof Error ? err.message : "Erreur lors de l'envoi"
    return NextResponse.json({ error: message }, { status: 500 })
  }

  await prisma.email.update({
    where: { id: emailId },
    data: { status: 'sent', sentAt: new Date() },
  })

  return NextResponse.json({ success: true })
}
