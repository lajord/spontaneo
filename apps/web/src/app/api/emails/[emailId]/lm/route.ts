import { NextRequest } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { readLmFile } from '@/lib/file-storage'

export async function GET(_req: NextRequest, { params }: { params: Promise<{ emailId: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return new Response('Non autorisé', { status: 401 })

  const { emailId } = await params

  const email = await prisma.email.findFirst({
    where: { id: emailId },
    include: { campaign: { select: { userId: true } } },
  })

  if (!email || email.campaign.userId !== session.user.id) {
    return new Response('Introuvable', { status: 404 })
  }

  const buffer = await readLmFile(email.campaign.userId, emailId)
  if (!buffer) return new Response('Fichier non trouvé', { status: 404 })

  return new Response(new Uint8Array(buffer), {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'Content-Disposition': `inline; filename="lettre-motivation.docx"`,
      'Cache-Control': 'private, no-cache',
    },
  })
}
