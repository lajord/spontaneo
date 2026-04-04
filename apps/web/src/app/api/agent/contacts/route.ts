import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { authorizeAgentRoute } from '@/lib/agent-auth'

interface ContactInput {
  name: string
  firstName?: string
  lastName?: string
  email?: string
  title?: string
  specialty?: string
  phone?: string
  linkedin?: string
  emailStatus?: string
  source?: string
  qualityScore?: number
  qualityReason?: string
  isDecisionMaker?: boolean
}

interface SaveContactsBody {
  jobId?: string
  companyDomain?: string
  companyUrl?: string
  companyName?: string
  agentCandidateId?: string
  contacts: ContactInput[]
}

function normalizeDomain(url?: string): string | null {
  if (!url) return null
  let value = url.toLowerCase().trim().replace(/\/$/, '')
  for (const prefix of ['https://www.', 'http://www.', 'https://', 'http://']) {
    if (value.startsWith(prefix)) value = value.slice(prefix.length)
  }
  return value.split('/')[0] || null
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

export async function POST(req: NextRequest) {
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  let body: SaveContactsBody
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  const { jobId, companyDomain, companyUrl, companyName, agentCandidateId, contacts } = body

  if (!jobId) return NextResponse.json({ error: 'jobId requis' }, { status: 400 })
  if (!Array.isArray(contacts) || contacts.length === 0) {
    return NextResponse.json({ error: 'contacts doit etre une liste non vide' }, { status: 400 })
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

  let candidateId = agentCandidateId
  if (!candidateId && companyDomain) {
    const domain = normalizeDomain(companyDomain)
    if (domain) {
      const candidate = await prisma.agentCandidate.findFirst({
        where: { userId: job.userId, jobId, domain },
        select: { id: true },
      })
      candidateId = candidate?.id ?? undefined
    }
  }

  if (!candidateId && companyUrl) {
    const domain = normalizeDomain(companyUrl)
    if (domain) {
      const candidate = await prisma.agentCandidate.findFirst({
        where: { userId: job.userId, jobId, domain },
        select: { id: true },
      })
      candidateId = candidate?.id ?? undefined
    }
  }

  if (!candidateId && companyName) {
    const normalizedCompanyName = normalizeName(companyName)
    if (normalizedCompanyName) {
      const candidates = await prisma.agentCandidate.findMany({
        where: { userId: job.userId, jobId },
        select: { id: true, name: true },
        take: 500,
      })
      const candidate = candidates.find((item) => normalizeName(item.name) === normalizedCompanyName)
      candidateId = candidate?.id
    }
  }

  if (!candidateId) {
    return NextResponse.json(
      { error: 'Impossible de resoudre agentCandidateId. Fournir agentCandidateId, companyDomain, companyUrl ou companyName.' },
      { status: 400 },
    )
  }

  const candidate = await prisma.agentCandidate.findFirst({
    where: { id: candidateId, userId: job.userId, jobId },
    select: { id: true },
  })
  if (!candidate) {
    return NextResponse.json({ error: 'AgentCandidate introuvable pour ce job' }, { status: 404 })
  }

  const existingContacts = await prisma.agentContact.findMany({
    where: { agentCandidateId: candidateId },
    select: { email: true },
  })
  const existingEmails = new Set<string>(
    existingContacts
      .map((contact) => normalizeEmail(contact.email))
      .filter((email): email is string => !!email),
  )

  const toInsert = contacts.filter((contact) => {
    const email = normalizeEmail(contact.email)
    if (email && existingEmails.has(email)) return false
    if (email) existingEmails.add(email)
    return true
  })

  if (toInsert.length === 0) {
    return NextResponse.json({ added: 0, duplicates: contacts.length, total: existingContacts.length })
  }

  const created = await prisma.agentContact.createMany({
    data: toInsert.map((contact) => ({
      agentCandidateId: candidateId!,
      userId: job.userId,
      name: contact.name,
      firstName: contact.firstName ?? null,
      lastName: contact.lastName ?? null,
      email: normalizeEmail(contact.email),
      title: contact.title ?? null,
      specialty: contact.specialty ?? null,
      phone: contact.phone ?? null,
      linkedin: contact.linkedin ?? null,
      emailStatus: contact.emailStatus ?? null,
      source: contact.source ?? null,
      qualityScore: contact.qualityScore ?? null,
      qualityReason: contact.qualityReason ?? null,
      isDecisionMaker: contact.isDecisionMaker ?? false,
    })),
    skipDuplicates: true,
  })

  await prisma.agentCandidate.update({
    where: { id: candidateId },
    data: { status: 'enriched' },
  })

  const total = await prisma.agentContact.count({ where: { agentCandidateId: candidateId } })
  const duplicates = contacts.length - created.count

  return NextResponse.json({
    added: created.count,
    duplicates,
    total,
    agentCandidateId: candidateId,
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

  const contacts = await prisma.agentContact.findMany({
    where: {
      ...(access.kind === 'session' ? { userId: access.userId } : {}),
      ...(jobId ? { agentCandidate: { jobId } } : {}),
      ...(agentCandidateId ? { agentCandidateId } : {}),
    },
    include: {
      agentCandidate: {
        select: { name: true, domain: true, city: true, websiteUrl: true, jobId: true },
      },
    },
    orderBy: { createdAt: 'desc' },
    take: 500,
  })

  return NextResponse.json({ count: contacts.length, contacts })
}
