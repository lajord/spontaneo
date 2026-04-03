import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { authorizeAgentRoute } from '@/lib/agent-auth'

interface DraftInput {
  agentCandidateId: string
  name: string
  firstName?: string
  lastName?: string
  email?: string
  title?: string
  specialty?: string
  city?: string
  contactType?: string
  isTested?: boolean
  sourceStage?: string
  sourceTool?: string
  sourceUrl?: string
}

interface SaveDraftsBody {
  jobId?: string
  drafts: DraftInput[]
}

function normalizeEmail(email?: string | null): string | null {
  if (!email) return null
  const trimmed = email.toLowerCase().trim()
  return trimmed || null
}

function normalizeName(name?: string | null): string | null {
  if (!name) return null
  const trimmed = name.toLowerCase().trim().replace(/\s+/g, ' ')
  return trimmed || null
}

function mergeDraft(existing: Record<string, unknown>, incoming: DraftInput) {
  const updateData: Record<string, unknown> = {}

  const assignIfEmpty = (key: keyof DraftInput, existingKey = key) => {
    const current = existing[existingKey as string]
    const next = incoming[key]
    if ((current === null || current === undefined || current === '') && next !== undefined && next !== null && `${next}`.trim() !== '') {
      updateData[existingKey as string] = next
    }
  }

  assignIfEmpty('firstName')
  assignIfEmpty('lastName')
  assignIfEmpty('email')
  assignIfEmpty('title')
  assignIfEmpty('specialty')
  assignIfEmpty('city')
  assignIfEmpty('sourceTool')
  assignIfEmpty('sourceUrl')

  if (!existing['contactType'] && incoming.contactType) {
    updateData.contactType = incoming.contactType
  }
  if (!existing['sourceStage'] && incoming.sourceStage) {
    updateData.sourceStage = incoming.sourceStage
  }
  if (!existing['isTested'] && incoming.isTested) {
    updateData.isTested = true
  }

  return updateData
}

export async function POST(req: NextRequest) {
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  let body: SaveDraftsBody
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  const { jobId, drafts } = body

  if (!jobId) return NextResponse.json({ error: 'jobId requis' }, { status: 400 })
  if (!Array.isArray(drafts) || drafts.length === 0) {
    return NextResponse.json({ error: 'drafts doit etre une liste non vide' }, { status: 400 })
  }

  const job = await prisma.job.findFirst({
    where: { id: jobId, type: 'agent_search' },
    select: { id: true, userId: true },
  })

  if (!job) {
    return NextResponse.json({ error: 'Job agent introuvable' }, { status: 404 })
  }

  if (access.kind === 'session' && access.userId !== job.userId) {
    return NextResponse.json({ error: 'Non autorise' }, { status: 403 })
  }

  const candidateIds = [...new Set(drafts.map((draft) => draft.agentCandidateId).filter(Boolean))]
  const candidates = await prisma.agentCandidate.findMany({
    where: {
      id: { in: candidateIds },
      userId: job.userId,
      jobId,
    },
    select: { id: true, campaignId: true },
  })

  const candidateMap = new Map(candidates.map((candidate) => [candidate.id, candidate]))
  const existingDrafts = await prisma.agentContactDraft.findMany({
    where: { agentCandidateId: { in: candidateIds } },
  })

  const existingByCandidate = new Map<string, Record<string, unknown>[]>()
  for (const draft of existingDrafts as unknown as Record<string, unknown>[]) {
    const list = existingByCandidate.get(String(draft.agentCandidateId)) ?? []
    list.push(draft)
    existingByCandidate.set(String(draft.agentCandidateId), list)
  }

  let added = 0
  let updated = 0
  let ignored = 0
  let rejected = 0
  const errors: string[] = []

  for (const [index, draft] of drafts.entries()) {
    if (!draft.agentCandidateId) {
      rejected += 1
      errors.push(`entree ${index + 1}: agentCandidateId manquant`)
      continue
    }
    if (!draft.name?.trim()) {
      rejected += 1
      errors.push(`entree ${index + 1}: name manquant`)
      continue
    }

    const candidate = candidateMap.get(draft.agentCandidateId)
    if (!candidate) {
      rejected += 1
      errors.push(`entree ${index + 1}: agentCandidateId introuvable pour ce job`)
      continue
    }

    const draftsForCandidate = existingByCandidate.get(draft.agentCandidateId) ?? []
    const email = normalizeEmail(draft.email)
    const name = normalizeName(draft.name)

    const match = draftsForCandidate.find((item) => {
      const itemEmail = normalizeEmail((item.email as string | null) ?? null)
      const itemName = normalizeName((item.name as string | null) ?? null)
      if (email && itemEmail) return email === itemEmail
      return !!name && !!itemName && name === itemName
    })

    if (match) {
      const updateData = mergeDraft(match, {
        ...draft,
        email: email ?? undefined,
      })
      if (Object.keys(updateData).length === 0) {
        ignored += 1
        continue
      }
      await prisma.agentContactDraft.update({
        where: { id: String(match.id) },
        data: updateData,
      })
      Object.assign(match, updateData)
      updated += 1
      continue
    }

    const created = await prisma.agentContactDraft.create({
      data: {
        agentCandidateId: draft.agentCandidateId,
        userId: job.userId,
        campaignId: candidate.campaignId ?? null,
        name: draft.name.trim(),
        firstName: draft.firstName?.trim() || null,
        lastName: draft.lastName?.trim() || null,
        email: email,
        title: draft.title?.trim() || null,
        specialty: draft.specialty?.trim() || null,
        city: draft.city?.trim() || null,
        contactType: draft.contactType?.trim() || 'personal',
        isTested: !!draft.isTested,
        sourceStage: draft.sourceStage?.trim() || '3A',
        sourceTool: draft.sourceTool?.trim() || null,
        sourceUrl: draft.sourceUrl?.trim() || null,
      },
    })
    draftsForCandidate.push(created as unknown as Record<string, unknown>)
    existingByCandidate.set(draft.agentCandidateId, draftsForCandidate)
    added += 1
  }

  return NextResponse.json({
    added,
    updated,
    ignored,
    rejected,
    errors,
  })
}

export async function GET(req: NextRequest) {
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const jobId = searchParams.get('jobId')
  const agentCandidateId = searchParams.get('agentCandidateId')

  if (access.kind === 'internal' && !jobId) {
    return NextResponse.json({ error: 'jobId requis pour un appel interne' }, { status: 400 })
  }

  const drafts = await prisma.agentContactDraft.findMany({
    where: {
      ...(access.kind === 'session' ? { userId: access.userId } : {}),
      ...(agentCandidateId ? { agentCandidateId } : {}),
      ...(jobId ? { agentCandidate: { jobId } } : {}),
    },
    orderBy: { updatedAt: 'desc' },
    take: 500,
  })

  return NextResponse.json({ count: drafts.length, drafts })
}
