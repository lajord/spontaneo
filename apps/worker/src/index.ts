import http from 'http'
import { setGlobalDispatcher, Agent } from 'undici'
import { prisma } from './eventStore'
import { runEnrichJob, JobPayload } from './enrichJob'

// Timeouts undici pour les appels longs vers FastAPI (Firecrawl/Gemini)
setGlobalDispatcher(new Agent({
  headersTimeout: 15 * 60 * 1000,
  bodyTimeout: 20 * 60 * 1000,
}))

const PORT = parseInt(process.env.WORKER_PORT ?? '3001')
const WORKER_SECRET = process.env.WORKER_SECRET ?? ''
const MAX_CONCURRENT = 2
const POLL_INTERVAL_MS = parseInt(process.env.POLL_INTERVAL_MS ?? '15000')
const STALE_THRESHOLD_MS = 60 * 60 * 1000 // 1h

const activeJobIds = new Set<string>()
let pollTimer: ReturnType<typeof setTimeout> | null = null

// ── Récupération des jobs bloqués (crash du worker) ─────────────────────────

async function recoverStaleJobs(): Promise<void> {
  const cutoff = new Date(Date.now() - STALE_THRESHOLD_MS)
  const result = await prisma.job.updateMany({
    where: {
      status: 'running',
      startedAt: { lt: cutoff },
    },
    data: {
      status: 'pending',
      startedAt: null,
    },
  })
  if (result.count > 0) {
    console.log(`[worker] Reset ${result.count} stale job(s) to pending`)
  }
}

// ── Claim atomique du prochain job pending (FIFO) ───────────────────────────

async function claimNextJob(): Promise<string | null> {
  if (activeJobIds.size >= MAX_CONCURRENT) return null

  const pendingJob = await prisma.job.findFirst({
    where: {
      status: 'pending',
      id: { notIn: Array.from(activeJobIds) },
    },
    orderBy: { createdAt: 'asc' },
    select: { id: true },
  })

  if (!pendingJob) return null

  // Optimistic lock : ne passe à running que si encore pending
  const claimed = await prisma.job.updateMany({
    where: { id: pendingJob.id, status: 'pending' },
    data: { status: 'running', startedAt: new Date() },
  })

  if (claimed.count === 0) return null
  return pendingJob.id
}

// ── Exécution d'un job ──────────────────────────────────────────────────────

async function handleJob(jobId: string): Promise<void> {
  console.log(`[worker] Starting job ${jobId}`)
  try {
    const job = await prisma.job.findUnique({
      where: { id: jobId },
      select: { campaignId: true, payload: true },
    })

    if (!job) {
      console.error(`[worker] Job ${jobId} not found in DB`)
      return
    }

    const payload = (job.payload ?? {}) as Record<string, unknown>
    const jobPayload: JobPayload = {
      jobId,
      campaignId: job.campaignId,
      links: (payload.links as JobPayload['links']) ?? {},
      userMailTemplate: (payload.userMailTemplate as string) ?? null,
      userMailSubject: (payload.userMailSubject as string) ?? null,
    }

    await runEnrichJob(jobPayload)
    console.log(`[worker] Completed job ${jobId}`)
  } catch (err) {
    console.error(`[worker] Failed job ${jobId}:`, err)
    await prisma.job.update({
      where: { id: jobId },
      data: { status: 'failed', error: String(err), completedAt: new Date() },
    }).catch(() => {})
  } finally {
    activeJobIds.delete(jobId)
    // Vérifier immédiatement s'il y a un prochain job
    pollForJobs()
  }
}

// ── Boucle de polling ───────────────────────────────────────────────────────

async function pollForJobs(): Promise<void> {
  try {
    await recoverStaleJobs()

    while (activeJobIds.size < MAX_CONCURRENT) {
      const jobId = await claimNextJob()
      if (!jobId) break

      activeJobIds.add(jobId)
      console.log(`[worker] Picked up job ${jobId}`)
      handleJob(jobId) // fire and forget
    }
  } catch (err) {
    console.error('[worker] Poll error:', err)
  }

  schedulePoll()
}

function schedulePoll(): void {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(pollForJobs, POLL_INTERVAL_MS)
}

function nudge(): void {
  if (pollTimer) clearTimeout(pollTimer)
  pollForJobs()
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log(`[worker] Starting — poll every ${POLL_INTERVAL_MS / 1000}s, max ${MAX_CONCURRENT} concurrent jobs`)

  // Serveur HTTP minimal : health check + nudge
  const server = http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ ok: true, activeJobs: activeJobIds.size, maxConcurrent: MAX_CONCURRENT }))
      return
    }

    if (req.method === 'POST' && req.url === '/nudge') {
      if (WORKER_SECRET && req.headers['x-worker-secret'] !== WORKER_SECRET) {
        res.writeHead(401).end()
        return
      }
      nudge()
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ ok: true }))
      return
    }

    res.writeHead(404).end()
  })

  server.listen(PORT, () => {
    console.log(`[worker] HTTP server on port ${PORT} (health + nudge)`)
  })

  // Premier poll immédiat (rattrape les jobs perdus au démarrage)
  await pollForJobs()

  // Shutdown gracieux
  const shutdown = async (signal: string) => {
    console.log(`[worker] ${signal} received, shutting down...`)
    if (pollTimer) clearTimeout(pollTimer)
    server.close()

    if (activeJobIds.size > 0) {
      console.log(`[worker] Waiting for ${activeJobIds.size} active job(s)...`)
      const deadline = setTimeout(() => {
        console.log('[worker] Shutdown timeout, forcing exit')
        process.exit(1)
      }, 30_000)

      await new Promise<void>(resolve => {
        const check = () => {
          if (activeJobIds.size === 0) { clearTimeout(deadline); resolve() }
          else setTimeout(check, 1000)
        }
        check()
      })
    }

    await prisma.$disconnect()
    process.exit(0)
  }

  process.on('SIGTERM', () => shutdown('SIGTERM'))
  process.on('SIGINT', () => shutdown('SIGINT'))
}

main().catch(err => {
  console.error('[worker] Fatal error:', err)
  process.exit(1)
})
