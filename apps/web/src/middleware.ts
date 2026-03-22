import { NextRequest, NextResponse } from 'next/server'
import { betterFetch } from '@better-fetch/fetch'
import type { Session } from '@/lib/auth'

const PROTECTED = ['/dashboard', '/campaigns', '/settings', '/admin', '/agent']
const AUTH_PAGES = ['/login', '/register']
const ADMIN_ONLY = ['/admin']

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

  // Block non-admin users from admin routes
  const isAdminRoute = ADMIN_ONLY.some((p) => pathname.startsWith(p))
  if (isAdminRoute && session && (session.user as any).role !== 'admin') {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/campaigns/:path*', '/settings/:path*', '/admin/:path*', '/agent/:path*', '/login', '/register'],
}
