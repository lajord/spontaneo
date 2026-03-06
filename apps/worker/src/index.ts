import http from 'http'
import { setGlobalDispatcher, Agent } from 'undici'
import { prisma } from './eventStore'
import { runEnrichJob, JobPayload } from './enrichJob'

// Augmente les timeouts undici (fetch natif Node.js) pour les appels longs vers FastAPI
// Par défaut headersTimeout = 30s ce qui est trop court pour Firecrawl/Gemini
setGlobalDispatcher(new Agent({
  headersTimeout: 15 * 60 * 1000, // 15 minutes
  bodyTimeout: 20 * 60 * 1000,    // 20 minutes
}))

const PORT = parseInt(process.env.WORKER_PORT ?? '3001')
const WORKER_SECRET = process.env.WORKER_SECRET ?? ''

// Max concurrent jobs across all users
const MAX_CONCURRENT = parseInt(process.env.WORKER_CONCURRENCY ?? '10')
let activeJobs = 0

async function handleJob(payload: JobPayload) {
  const { jobId, campaignId } = payload
  console.log(`[worker] Starting job ${jobId} for campaign ${campaignId}`)
  try {
    await runEnrichJob(payload)
    console.log(`[worker] Completed job ${jobId}`)
  } catch (err) {
    console.error(`[worker] Failed job ${jobId}:`, err)
    await prisma.job.update({
      where: { id: jobId },
      data: { status: 'failed', error: String(err), completedAt: new Date() },
    }).catch(() => {})
  } finally {
    activeJobs--
  }
}

async function main() {
  const server = http.createServer((req, res) => {
    if (req.method !== 'POST' || req.url !== '/process') {
      res.writeHead(404).end()
      return
    }

    if (WORKER_SECRET && req.headers['x-worker-secret'] !== WORKER_SECRET) {
      res.writeHead(401).end()
      return
    }

    let body = ''
    req.on('data', chunk => { body += chunk })
    req.on('end', () => {
      let payload: JobPayload
      try {
        payload = JSON.parse(body)
      } catch {
        res.writeHead(400).end()
        return
      }

      if (activeJobs >= MAX_CONCURRENT) {
        res.writeHead(429, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ error: 'Worker at capacity' }))
        return
      }

      activeJobs++
      handleJob(payload) // fire and forget

      res.writeHead(202, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ accepted: true }))
    })
  })

  server.listen(PORT, () => {
    console.log(`[worker] HTTP server listening on port ${PORT}`)
  })

  const shutdown = async (signal: string) => {
    console.log(`[worker] Received ${signal}, shutting down gracefully...`)
    server.close()
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
