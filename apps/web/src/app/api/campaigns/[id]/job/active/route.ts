import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  const { id } = await params
  const { searchParams } = new URL(req.url)
  const type = searchParams.get('type')

  const activeJob = await prisma.job.findFirst({
    where: {
      campaignId: id,
      userId: session.user.id,
      ...(type ? { type } : {}),
      status: { in: ['pending', 'running', 'paused'] },
    },
    select: {
      id: true,
      status: true,
      type: true,
      payload: true,
      cancelRequestedAt: true,
    },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json({ job: activeJob })
}
