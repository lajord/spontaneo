import { appendJobEvent, prisma } from './eventStore'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'
const CANCEL_POLL_MS = 1000

export type AgentJobPayload = {
  jobId: string
  userId: string
  campaignId: string
  secteur: string
  sousSecteur: string
  jobTitle: string
  location: string
  creditBudget: number | null
  devMode: boolean
}

async function isCancelRequested(jobId: string): Promise<boolean> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { cancelRequestedAt: true, status: true },
  })
  return !!job?.cancelRequestedAt || job?.status === 'cancelled'
}

export async function runAgentJob(payload: AgentJobPayload): Promise<void> {
  const controller = new AbortController()
  const decoder = new TextDecoder()
  let buffer = ''

  const cancelWatcher = setInterval(() => {
    isCancelRequested(payload.jobId)
      .then((cancelRequested) => {
        if (cancelRequested) controller.abort()
      })
      .catch(() => {})
  }, CANCEL_POLL_MS)

  try {
    await appendJobEvent(payload.jobId, {
      type: 'job_started',
      phase: 'AGENT',
      message: 'Job agent demarre',
    })

    const res = await fetch(`${AI_SERVICE_URL}/api/v1/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        secteur: payload.secteur,
        sous_secteur: payload.sousSecteur,
        job_title: payload.jobTitle,
        location: payload.location,
        credit_budget: payload.creditBudget,
        dev_mode: payload.devMode,
        user_id: payload.userId,
        job_id: payload.jobId,
        campaign_id: payload.campaignId,
      }),
    })

    if (!res.ok || !res.body) {
      throw new Error(`AI service error ${res.status}`)
    }

    const reader = res.body.getReader()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      if (await isCancelRequested(payload.jobId)) {
        controller.abort()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          await appendJobEvent(payload.jobId, event)
        } catch {
          // ignore malformed SSE payload
        }
      }
    }

    if (await isCancelRequested(payload.jobId)) {
      await appendJobEvent(payload.jobId, { type: 'cancelled', message: 'Job agent annule' })
      await prisma.job.update({
        where: { id: payload.jobId },
        data: { status: 'cancelled', completedAt: new Date() },
      })
      return
    }

    await prisma.job.update({
      where: { id: payload.jobId },
      data: { status: 'completed', completedAt: new Date(), error: null },
    })
  } catch (err) {
    if (controller.signal.aborted || (await isCancelRequested(payload.jobId))) {
      await appendJobEvent(payload.jobId, { type: 'cancelled', message: 'Job agent annule' }).catch(() => {})
      await prisma.job.update({
        where: { id: payload.jobId },
        data: { status: 'cancelled', completedAt: new Date() },
      }).catch(() => {})
      return
    }
    throw err
  } finally {
    clearInterval(cancelWatcher)
  }
}
