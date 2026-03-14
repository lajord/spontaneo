import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = await params

  // Checks for any job that is pending, running, or paused.
  const activeJob = await prisma.job.findFirst({
    where: {
      campaignId: id,
      userId: session.user.id,
      status: { in: ['pending', 'running', 'paused'] },
    },
    select: {
      id: true,
      status: true,
      payload: true,
    },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json({ job: activeJob })
}
