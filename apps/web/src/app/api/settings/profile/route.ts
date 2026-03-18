import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function PATCH(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { name } = await req.json()
  if (!name?.trim()) return NextResponse.json({ error: 'Nom invalide' }, { status: 400 })

  await prisma.user.update({
    where: { id: session.user.id },
    data: { name: name.trim() },
  })

  return NextResponse.json({ success: true })
}
