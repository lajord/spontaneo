import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { headers } from 'next/headers'

export async function PATCH(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { currentPassword, newPassword } = await req.json()
  if (!currentPassword || !newPassword) {
    return NextResponse.json({ error: 'Champs manquants' }, { status: 400 })
  }
  if (newPassword.length < 8) {
    return NextResponse.json({ error: 'Le mot de passe doit faire au moins 8 caractères' }, { status: 400 })
  }

  try {
    await auth.api.changePassword({
      headers: await headers(),
      body: { currentPassword, newPassword, revokeOtherSessions: false },
    })
    return NextResponse.json({ success: true })
  } catch {
    return NextResponse.json({ error: 'Mot de passe actuel incorrect' }, { status: 400 })
  }
}
