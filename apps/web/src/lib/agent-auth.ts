import { NextRequest } from 'next/server'
import { auth } from '@/lib/auth'
import { headers } from 'next/headers'

export type AgentRouteAccess =
  | { kind: 'internal' }
  | { kind: 'session'; userId: string }

function getInternalToken(): string | null {
  return process.env.AGENT_INTERNAL_API_TOKEN ?? process.env.CRON_SECRET ?? null
}

function isLocalDevInternalRequest(req: NextRequest): boolean {
  if (process.env.NODE_ENV === 'production') return false
  if (getInternalToken()) return false

  const devHeader = req.headers.get('x-agent-dev-internal')
  if (devHeader !== '1') return false

  const host = req.headers.get('host') ?? req.nextUrl.host ?? ''
  const hostname = host.split(':')[0]?.toLowerCase()
  return hostname === 'localhost' || hostname === '127.0.0.1'
}

export async function authorizeAgentRoute(req: NextRequest): Promise<AgentRouteAccess | null> {
  const internalToken = getInternalToken()
  const authorization = req.headers.get('authorization')

  if (internalToken && authorization === `Bearer ${internalToken}`) {
    return { kind: 'internal' }
  }

  if (isLocalDevInternalRequest(req)) {
    return { kind: 'internal' }
  }

  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) {
    return null
  }

  return { kind: 'session', userId: session.user.id }
}
