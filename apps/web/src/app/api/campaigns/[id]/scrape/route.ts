import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

interface CompanyEvent {
  nom: string
  adresse?: string
  site_web?: string
  telephone?: string
  source?: string
}

function isAlreadyContacted(
  company: CompanyEvent,
  contactedNames: Set<string>,
  contactedDomains: Set<string>,
): boolean {
  if (contactedNames.has(company.nom.toLowerCase().trim())) return true
  if (company.site_web) {
    try {
      const domain = new URL(company.site_web).hostname.replace(/^www\./, '')
      if (contactedDomains.has(domain)) return true
    } catch { /* ignore */ }
  }
  return false
}

export async function POST(_req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const { id } = params
  const campaign = await prisma.campaign.findFirst({
    where: { id, userId: session.user.id },
  })
  if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

  // Charger les entreprises déjà contactées
  const contacted = await (prisma as any).contactedCompany.findMany({
    where: { userId: session.user.id },
    select: { companyName: true, domain: true },
  })
  const contactedNames = new Set<string>(contacted.map((c: any) => c.companyName.toLowerCase().trim()))
  const contactedDomains = new Set<string>(contacted.map((c: any) => c.domain).filter(Boolean))

  // Appel streaming vers le service IA
  const response = await fetch(`${AI_SERVICE_URL}/api/v1/recuperation-data/search/apollo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      secteur: campaign.jobTitle,
      localisation: campaign.location,
      radius: campaign.radius,
      prompt: campaign.prompt ?? null,
      sectors: campaign.sectors ?? [],
      categories: campaign.categories ?? [],
    }),
    signal: AbortSignal.timeout(600_000), // 10 minutes (streaming long)
  })

  if (!response.ok || !response.body) {
    return NextResponse.json({ error: 'Erreur service IA' }, { status: 502 })
  }

  // Stream : lire les events SSE du service IA, sauvegarder en DB, forwarder au frontend
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder()

      function send(data: Record<string, unknown>) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`))
      }

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue

            try {
              const event = JSON.parse(jsonStr)

              if (event.type === 'company' && event.company) {
                const c: CompanyEvent = event.company
                if (isAlreadyContacted(c, contactedNames, contactedDomains)) continue

                // Sauvegarder en DB
                const saved = await prisma.company.create({
                  data: {
                    campaignId: id,
                    name: c.nom,
                    address: c.adresse ?? null,
                    website: c.site_web ?? null,
                    phone: c.telephone ?? null,
                    sector: campaign.jobTitle,
                    source: c.source ?? null,
                  },
                })

                send({ type: 'company', company: saved })
              } else if (event.type === 'params') {
                send(event)
              } else if (event.type === 'done') {
                await prisma.campaign.update({ where: { id }, data: { status: 'scraped' } })
                const count = await prisma.company.count({ where: { campaignId: id } })
                send({ type: 'done', total: count })
              }
            } catch {
              // Ignorer les events mal formés
            }
          }
        }
      } catch (err) {
        console.error('[SCRAPE STREAM] Erreur:', err)
        send({ type: 'error', error: 'Erreur lors du scraping' })
      } finally {
        controller.close()
      }
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
