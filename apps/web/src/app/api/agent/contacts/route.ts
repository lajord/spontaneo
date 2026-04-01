import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

interface ContactInput {
  name: string
  firstName?: string
  lastName?: string
  email?: string
  title?: string
  phone?: string
  linkedin?: string
  emailStatus?: string
  source?: string
  qualityScore?: number
  qualityReason?: string
  isDecisionMaker?: boolean
}

interface SaveContactsBody {
  userId: string
  jobId?: string
  companyDomain?: string
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

export async function POST(req: NextRequest) {
  let body: SaveContactsBody
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  const { userId, jobId, companyDomain, agentCandidateId, contacts } = body

  if (!userId) return NextResponse.json({ error: 'userId requis' }, { status: 400 })
  if (!jobId) return NextResponse.json({ error: 'jobId requis' }, { status: 400 })
  if (!Array.isArray(contacts) || contacts.length === 0) {
    return NextResponse.json({ error: 'contacts doit etre une liste non vide' }, { status: 400 })
  }

  let candidateId = agentCandidateId
  if (!candidateId && companyDomain) {
    const domain = normalizeDomain(companyDomain)
    if (domain) {
      const candidate = await prisma.agentCandidate.findFirst({
        where: { userId, jobId, domain },
        select: { id: true },
      })
      candidateId = candidate?.id ?? undefined
    }
  }

  if (!candidateId) {
    return NextResponse.json(
      { error: 'Impossible de resoudre agentCandidateId. Fournir agentCandidateId ou companyDomain.' },
      { status: 400 },
    )
  }

  const candidate = await prisma.agentCandidate.findFirst({
    where: { id: candidateId, userId, jobId },
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
      userId,
      name: contact.name,
      firstName: contact.firstName ?? null,
      lastName: contact.lastName ?? null,
      email: normalizeEmail(contact.email),
      title: contact.title ?? null,
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
  const { searchParams } = new URL(req.url)
  const userId = searchParams.get('userId')
  const jobId = searchParams.get('jobId')
  const agentCandidateId = searchParams.get('agentCandidateId')

  if (!userId) return NextResponse.json({ error: 'userId requis' }, { status: 400 })

  const contacts = await prisma.agentContact.findMany({
    where: {
      userId,
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
