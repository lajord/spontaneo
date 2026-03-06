import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const config = await prisma.emailConfig.findUnique({ where: { userId: session.user.id } })
  if (!config) return NextResponse.json({ connected: false })

  // Ne jamais exposer les tokens au frontend
  return NextResponse.json({
    connected: !!config.accessToken,
    provider: config.provider,
    oauthEmail: config.oauthEmail,
  })
}
