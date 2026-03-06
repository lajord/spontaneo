import { NextRequest } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const POLL_INTERVAL_MS = 1000

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) {
    return new Response('Non autorisé', { status: 401 })
  }

  const { jobId } = await params

  // Vérifier que le job appartient au user
  const job = await prisma.job.findFirst({
    where: { id: jobId, userId: session.user.id },
    select: { id: true, status: true },
  })

  if (!job) {
    return new Response('Job introuvable', { status: 404 })
  }

  // Cursor de replay : fourni par EventSource via Last-Event-ID header
  const lastSeq = parseInt(req.headers.get('Last-Event-ID') ?? '0')

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    async start(controller) {
      let cursor = lastSeq
      let closed = false

      const enqueue = (id: number, data: object) => {
        if (closed) return
        try {
          controller.enqueue(encoder.encode(`id: ${id}\ndata: ${JSON.stringify(data)}\n\n`))
        } catch {
          closed = true
        }
      }

      const close = () => {
        if (closed) return
        closed = true
        try { controller.close() } catch { /* déjà fermé */ }
      }

      // 1. Replay des events historiques (depuis le cursor)
      const history = await prisma.jobEvent.findMany({
        where: { jobId, seq: { gt: cursor } },
        orderBy: { seq: 'asc' },
      })

      for (const evt of history) {
        enqueue(evt.seq, evt.payload as object)
        cursor = evt.seq
      }

      // Si le job est déjà terminé après le replay, on ferme
      const freshJob = await prisma.job.findUnique({
        where: { id: jobId },
        select: { status: true },
      })
      if (freshJob?.status === 'completed' || freshJob?.status === 'failed') {
        close()
        return
      }

      // 2. Polling pour les nouveaux events
      const poll = async () => {
        if (closed) return

        try {
          const [currentJob, newEvents] = await Promise.all([
            prisma.job.findUnique({ where: { id: jobId }, select: { status: true } }),
            prisma.jobEvent.findMany({
              where: { jobId, seq: { gt: cursor } },
              orderBy: { seq: 'asc' },
            }),
          ])

          for (const evt of newEvents) {
            enqueue(evt.seq, evt.payload as object)
            cursor = evt.seq
          }

          if (currentJob?.status === 'completed' || currentJob?.status === 'failed') {
            close()
            return
          }

          if (!closed) {
            setTimeout(poll, POLL_INTERVAL_MS)
          }
        } catch {
          close()
        }
      }

      setTimeout(poll, POLL_INTERVAL_MS)
    },
    cancel() {
      // Client déconnecté — EventSource reconnectera automatiquement avec Last-Event-ID
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  })
}
