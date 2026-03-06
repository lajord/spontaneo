import { NextRequest, NextResponse } from 'next/server'
import { betterFetch } from '@better-fetch/fetch'
import type { Session } from '@/lib/auth'

const PROTECTED = ['/dashboard', '/campaigns', '/settings']
const AUTH_PAGES = ['/login', '/register']

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  const isProtected = PROTECTED.some((p) => pathname.startsWith(p))
  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p))

  if (!isProtected && !isAuthPage) return NextResponse.next()

  const { data: session } = await betterFetch<Session>('/api/auth/get-session', {
    baseURL: request.nextUrl.origin,
    headers: { cookie: request.headers.get('cookie') ?? '' },
  })

  if (isProtected && !session) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  if (isAuthPage && session) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/campaigns/:path*', '/settings/:path*', '/login', '/register'],
}
