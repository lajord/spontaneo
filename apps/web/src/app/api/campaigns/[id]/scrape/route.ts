import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

export async function POST(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await prisma.campaign.findFirst({
    where: { id, userId: session.user.id },
  })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  // Appel Apollo via le service IA
  const response = await fetch(`${AI_SERVICE_URL}/api/v1/recuperation-data/search/apollo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      secteur: campaign.jobTitle,
      localisation: campaign.location,
      radius: campaign.radius,
      prompt: campaign.prompt ?? null,
      sectors: campaign.sectors ?? [],
    }),
    signal: AbortSignal.timeout(300_000), // 5 minutes
  })

  if (!response.ok) {
    return NextResponse.json({ error: 'Erreur service IA' }, { status: 502 })
  }

  const data = await response.json()
  const rawEntreprises: Array<{
    nom: string
    adresse?: string
    site_web?: string
    telephone?: string
    siren?: string
    code_naf?: string
    source?: string
  }> = data.entreprises ?? []

  // Filtrer les entreprises déjà contactées par ce user
  const contacted = await (prisma as any).contactedCompany.findMany({
    where: { userId: session.user.id },
    select: { companyName: true, domain: true }
  })
  const contactedNames = new Set(contacted.map((c: any) => c.companyName.toLowerCase().trim()))
  const contactedDomains = new Set(contacted.map((c: any) => c.domain).filter(Boolean))

  const entreprises = rawEntreprises.filter(e => {
    const nameStr = e.nom.toLowerCase().trim()
    if (contactedNames.has(nameStr)) return false
    if (e.site_web) {
      try {
        const url = new URL(e.site_web)
        // strip www. if present
        const domain = url.hostname.replace(/^www\./, '')
        if (contactedDomains.has(domain)) return false
      } catch {
        // ignore invalid urls
      }
    }
    return true
  })

  // Sauvegarde en base — createMany = 1 seul INSERT groupé, pas de timeout
  await prisma.company.createMany({
    data: entreprises.map((e) => ({
      campaignId: id,
      name: e.nom,
      address: e.adresse ?? null,
      website: e.site_web ?? null,
      phone: e.telephone ?? null,
      sector: campaign.jobTitle,
      siren: e.siren ?? null,
      codeNaf: e.code_naf ?? null,
      source: e.source ?? null,
    })),
  })

  await prisma.campaign.update({ where: { id }, data: { status: 'scraped' } })

  const companies = await prisma.company.findMany({ where: { campaignId: id } })

  return NextResponse.json({ total: companies.length, companies })
}
