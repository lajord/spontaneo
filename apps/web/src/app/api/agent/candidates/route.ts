import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

interface CompanyInput {
  name: string
  websiteUrl?: string
  domain?: string
  city?: string
  description?: string
  source?: string
}

interface SaveCandidatesBody {
  userId: string
  jobId?: string
  campaignId?: string
  secteur?: string
  jobTitle?: string
  location?: string
  companies: CompanyInput[]
}

function normalizeDomain(url?: string): string | null {
  if (!url) return null
  let value = url.toLowerCase().trim().replace(/\/$/, '')
  for (const prefix of ['https://www.', 'http://www.', 'https://', 'http://']) {
    if (value.startsWith(prefix)) value = value.slice(prefix.length)
  }
  return value.split('/')[0] || null
}

function normalizeName(name: string): string {
  return name.toLowerCase().trim().replace(/\s+/g, ' ')
}

export async function POST(req: NextRequest) {
  let body: SaveCandidatesBody
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  const { userId, jobId, campaignId, secteur, jobTitle, location, companies } = body

  if (!userId) return NextResponse.json({ error: 'userId requis' }, { status: 400 })
  if (!jobId) return NextResponse.json({ error: 'jobId requis' }, { status: 400 })
  if (!campaignId) return NextResponse.json({ error: 'campaignId requis' }, { status: 400 })
  if (!Array.isArray(companies) || companies.length === 0) {
    return NextResponse.json({ error: 'companies doit etre une liste non vide' }, { status: 400 })
  }

  const incomingDomains = companies
    .map((company) => normalizeDomain(company.websiteUrl || company.domain))
    .filter(Boolean) as string[]

  const existingByDomain = await prisma.agentCandidate.findMany({
    where: { jobId, domain: { in: incomingDomains } },
    select: { domain: true },
  })
  const existingDomains = new Set(existingByDomain.map((item) => item.domain).filter(Boolean))

  const incomingNames = companies
    .filter((company) => !normalizeDomain(company.websiteUrl || company.domain))
    .map((company) => normalizeName(company.name))

  const existingByName = incomingNames.length > 0
    ? await prisma.agentCandidate.findMany({
        where: { jobId, domain: null, name: { in: incomingNames } },
        select: { name: true },
      })
    : []
  const existingNames = new Set(existingByName.map((item) => normalizeName(item.name)))

  const toInsert = companies.filter((company) => {
    const domain = normalizeDomain(company.websiteUrl || company.domain)
    if (domain) return !existingDomains.has(domain)
    return !existingNames.has(normalizeName(company.name))
  })

  if (toInsert.length === 0) {
    const total = await prisma.agentCandidate.count({ where: { jobId } })
    return NextResponse.json({ added: 0, duplicates: companies.length, total })
  }

  const created = await prisma.agentCandidate.createMany({
    data: toInsert.map((company) => ({
      userId,
      jobId,
      campaignId,
      name: company.name,
      domain: normalizeDomain(company.websiteUrl || company.domain),
      websiteUrl: company.websiteUrl ?? null,
      city: company.city ?? null,
      description: company.description ? company.description.slice(0, 300) : null,
      source: company.source ?? null,
      secteur: secteur ?? null,
      jobTitle: jobTitle ?? null,
      location: location ?? null,
      status: 'pending',
    })),
    skipDuplicates: true,
  })

  const total = await prisma.agentCandidate.count({ where: { jobId } })
  const duplicates = companies.length - created.count

  return NextResponse.json({
    added: created.count,
    duplicates,
    total,
    message: `${created.count} nouvelles entreprises sauvegardees (total: ${total}, doublons ignores: ${duplicates}).`,
  })
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const userId = searchParams.get('userId')
  const jobId = searchParams.get('jobId')
  const campaignId = searchParams.get('campaignId')
  const status = searchParams.get('status')

  if (!userId) return NextResponse.json({ error: 'userId requis' }, { status: 400 })

  const candidates = await prisma.agentCandidate.findMany({
    where: {
      userId,
      ...(jobId ? { jobId } : {}),
      ...(campaignId ? { campaignId } : {}),
      ...(status ? { status } : {}),
    },
    orderBy: { createdAt: 'desc' },
    take: 500,
  })

  return NextResponse.json({ count: candidates.length, candidates })
}
