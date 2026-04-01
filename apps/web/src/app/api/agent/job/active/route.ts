import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  const job = await prisma.job.findFirst({
    where: {
      userId: session.user.id,
      type: 'agent_search',
      status: { in: ['pending', 'running'] },
    },
    select: {
      id: true,
      status: true,
      payload: true,
      cancelRequestedAt: true,
      createdAt: true,
    },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json({ job })
}
