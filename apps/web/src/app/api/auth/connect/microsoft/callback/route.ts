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

  let userId: string
  try {
    userId = Buffer.from(state, 'base64url').toString('utf-8')
  } catch {
    return NextResponse.redirect(`${appUrl}/settings?error=invalid_state`)
  }

  const redirectUri = `${appUrl}/api/auth/connect/microsoft/callback`

  // Échanger le code contre des tokens
  const tokenRes = await fetch('https://login.microsoftonline.com/common/oauth2/v2.0/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: process.env.MICROSOFT_CLIENT_ID!,
      client_secret: process.env.MICROSOFT_CLIENT_SECRET!,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code',
      scope: 'https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access',
    }),
  })
  const tokenData = await tokenRes.json()
  if (!tokenRes.ok) {
    return NextResponse.redirect(`${appUrl}/settings?error=${encodeURIComponent(tokenData.error ?? 'token_error')}`)
  }

  // Récupérer le profil (email) via Microsoft Graph
  const userRes = await fetch('https://graph.microsoft.com/v1.0/me', {
    headers: { Authorization: `Bearer ${tokenData.access_token}` },
  })
  const userData = await userRes.json()
  if (!userRes.ok) {
    return NextResponse.redirect(`${appUrl}/settings?error=userinfo_error`)
  }

  const oauthEmail = userData.mail ?? userData.userPrincipalName ?? null
  const tokenExpiry = new Date(Date.now() + tokenData.expires_in * 1000)

  await prisma.emailConfig.upsert({
    where: { userId },
    create: {
      userId,
      provider: 'microsoft',
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token ?? null,
      tokenExpiry,
      oauthEmail,
    },
    update: {
      provider: 'microsoft',
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token ?? undefined,
      tokenExpiry,
      oauthEmail,
    },
  })

  return NextResponse.redirect(`${appUrl}/settings?connected=microsoft`)
}
