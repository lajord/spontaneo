import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { headers } from 'next/headers'

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'
  const redirectUri = `${appUrl}/api/auth/connect/microsoft/callback`

  const state = Buffer.from(session.user.id).toString('base64url')

  const params = new URLSearchParams({
    client_id: process.env.MICROSOFT_CLIENT_ID!,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access',
    response_mode: 'query',
    state,
  })

  return NextResponse.redirect(`https://login.microsoftonline.com/common/oauth2/v2.0/authorize?${params}`)
}
