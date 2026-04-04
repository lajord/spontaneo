import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { authorizeAgentRoute } from '@/lib/agent-auth'

interface CompanyInput {
  name: string
  websiteUrl?: string
  website_url?: string
  website?: string
  url?: string
  domain?: string
  city?: string
  description?: string
  source?: string
}

interface SaveCandidatesBody {
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

function getCompanyWebsite(company: CompanyInput): string | undefined {
  return company.websiteUrl ?? company.website_url ?? company.website ?? company.url
}

export async function POST(req: NextRequest) {
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  let body: SaveCandidatesBody
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Corps de requete invalide' }, { status: 400 })
  }

  const { jobId, campaignId, secteur, jobTitle, location, companies } = body

  if (!jobId) return NextResponse.json({ error: 'jobId requis' }, { status: 400 })
  if (!Array.isArray(companies) || companies.length === 0) {
    return NextResponse.json({ error: 'companies doit etre une liste non vide' }, { status: 400 })
  }

  const job = await prisma.job.findFirst({
    where: { id: jobId, ...(campaignId ? { campaignId } : {}), type: 'agent_search' },
    select: { id: true, userId: true, campaignId: true, payload: true },
  })

  if (!job) {
    return NextResponse.json({ error: 'Job agent introuvable' }, { status: 404 })
  }

  if (access.kind === 'session' && access.userId !== job.userId) {
    return NextResponse.json({ error: 'Non autorise' }, { status: 403 })
  }

  const payload = (job.payload ?? {}) as Record<string, unknown>
  const resolvedSecteur = secteur ?? (typeof payload.secteur === 'string' ? payload.secteur : null)
  const resolvedJobTitle = jobTitle ?? (typeof payload.jobTitle === 'string' ? payload.jobTitle : null)
  const resolvedLocation = location ?? (typeof payload.location === 'string' ? payload.location : null)
  const targetCount = typeof payload.targetCount === 'number' && payload.targetCount > 0
    ? payload.targetCount
    : null
  const currentTotal = await prisma.agentCandidate.count({ where: { jobId } })
  const remainingSlots = targetCount === null ? null : Math.max(0, targetCount - currentTotal)

  if (remainingSlots === 0) {
    return NextResponse.json({ added: 0, duplicates: companies.length, total: currentTotal })
  }

  const incomingDomains = companies
    .map((company) => normalizeDomain(getCompanyWebsite(company) || company.domain))
    .filter(Boolean) as string[]

  const existingByDomain = await prisma.agentCandidate.findMany({
    where: { jobId, domain: { in: incomingDomains } },
    select: { domain: true },
  })
  const existingDomains = new Set(existingByDomain.map((item) => item.domain).filter(Boolean))

  const incomingNames = companies
    .filter((company) => !normalizeDomain(getCompanyWebsite(company) || company.domain))
    .map((company) => normalizeName(company.name))

  const existingByName = incomingNames.length > 0
    ? await prisma.agentCandidate.findMany({
        where: { jobId, domain: null, name: { in: incomingNames } },
        select: { name: true },
      })
    : []
  const existingNames = new Set(existingByName.map((item) => normalizeName(item.name)))

  const dedupedCompanies = companies.filter((company) => {
    const domain = normalizeDomain(getCompanyWebsite(company) || company.domain)
    if (domain) return !existingDomains.has(domain)
    return !existingNames.has(normalizeName(company.name))
  })

  const toInsert = remainingSlots === null
    ? dedupedCompanies
    : dedupedCompanies.slice(0, remainingSlots)

  if (toInsert.length === 0) {
    return NextResponse.json({ added: 0, duplicates: companies.length, total: currentTotal })
  }

  const created = await prisma.agentCandidate.createMany({
    data: toInsert.map((company) => ({
      userId: job.userId,
      jobId,
      campaignId: job.campaignId,
      name: company.name,
      domain: normalizeDomain(getCompanyWebsite(company) || company.domain),
      websiteUrl: getCompanyWebsite(company) ?? null,
      city: company.city ?? null,
      description: company.description ? company.description.slice(0, 300) : null,
      source: company.source ?? null,
      secteur: resolvedSecteur,
      jobTitle: resolvedJobTitle,
      location: resolvedLocation,
      status: 'pending',
    })),
    skipDuplicates: true,
  })

  // ── Sync Company records ───────────────────────────────────────────
  // Pour que le worker email-gen (qui lit campaign.companies) puisse traiter ces entreprises.
  if (job.campaignId) {
    await prisma.company.createMany({
      data: toInsert.map((company) => ({
        campaignId: job.campaignId!,
        name: company.name,
        website: getCompanyWebsite(company) ?? null,
        address: company.city ?? null,
        source: company.source ?? null,
        status: 'scraped',
      })),
      skipDuplicates: true,
    })
  }

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
  const access = await authorizeAgentRoute(req)
  if (!access) return NextResponse.json({ error: 'Non autorise' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const jobId = searchParams.get('jobId')
  const campaignId = searchParams.get('campaignId')
  const status = searchParams.get('status')

  if (access.kind === 'internal' && !jobId) {
    return NextResponse.json({ error: 'jobId requis pour un appel interne' }, { status: 400 })
  }

  const candidates = await prisma.agentCandidate.findMany({
    where: {
      ...(access.kind === 'session' ? { userId: access.userId } : {}),
      ...(jobId ? { jobId } : {}),
      ...(campaignId ? { campaignId } : {}),
      ...(status ? { status } : {}),
    },
    orderBy: { createdAt: 'desc' },
    take: 500,
  })

  return NextResponse.json({ count: candidates.length, candidates })
}
