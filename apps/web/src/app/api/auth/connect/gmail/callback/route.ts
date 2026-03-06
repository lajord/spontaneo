import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function GET(req: NextRequest) {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'
  const { searchParams } = new URL(req.url)
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const error = searchParams.get('error')

  if (error) return NextResponse.redirect(`${appUrl}/settings?error=${encodeURIComponent(error)}`)
  if (!code || !state) return NextResponse.redirect(`${appUrl}/settings?error=invalid_callback`)

  // Décoder l'userId depuis le state
  let userId: string
  try {
    userId = Buffer.from(state, 'base64url').toString('utf-8')
  } catch {
    return NextResponse.redirect(`${appUrl}/settings?error=invalid_state`)
  }

  const redirectUri = `${appUrl}/api/auth/connect/gmail/callback`

  // Échanger le code contre des tokens
  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code',
    }),
  })
  const tokenData = await tokenRes.json()
  if (!tokenRes.ok) {
    return NextResponse.redirect(`${appUrl}/settings?error=${encodeURIComponent(tokenData.error ?? 'token_error')}`)
  }

  // Récupérer l'adresse email de l'utilisateur Google
  const userRes = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${tokenData.access_token}` },
  })
  const userData = await userRes.json()
  if (!userRes.ok) {
    return NextResponse.redirect(`${appUrl}/settings?error=userinfo_error`)
  }

  const tokenExpiry = new Date(Date.now() + tokenData.expires_in * 1000)

  await prisma.emailConfig.upsert({
    where: { userId },
    create: {
      userId,
      provider: 'gmail',
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token ?? null,
      tokenExpiry,
      oauthEmail: userData.email,
    },
    update: {
      provider: 'gmail',
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token ?? undefined,
      tokenExpiry,
      oauthEmail: userData.email,
    },
  })

  return NextResponse.redirect(`${appUrl}/settings?connected=gmail`)
}
