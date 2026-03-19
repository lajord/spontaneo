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
  type_activite?: string
  score?: number
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

            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            let event: any
            try {
              event = JSON.parse(jsonStr)
            } catch {
              continue
            }

            console.log('[SCRAPE] event reçu:', event?.type, event?.company?.nom ?? '')

            if (event.type === 'company' && event.company) {
              const c = event.company as CompanyEvent
              if (isAlreadyContacted(c, contactedNames, contactedDomains)) {
                console.log('[SCRAPE] ignorée (déjà contactée):', c.nom)
                continue
              }

              try {
                const saved = await prisma.company.create({
                  data: {
                    campaignId: id,
                    name: c.nom,
                    address: c.adresse ?? null,
                    website: c.site_web ?? null,
                    phone: c.telephone ?? null,
                    sector: campaign.jobTitle,
                    source: c.source ?? null,
                    score: c.score ?? null,
                  },
                })
                console.log('[SCRAPE] sauvegardée + forwardée:', c.nom)
                send({ type: 'company', company: saved, tier: event.tier ?? 'high', score: c.score ?? null })
              } catch (dbErr) {
                console.error('[SCRAPE] Erreur Prisma company.create:', c.nom, dbErr)
                send({
                  type: 'company',
                  company: {
                    id: `tmp-${Math.random().toString(36).slice(2, 10)}`,
                    name: c.nom,
                    address: c.adresse ?? null,
                    website: c.site_web ?? null,
                    phone: c.telephone ?? null,
                    siren: null,
                    source: c.source ?? null,
                    status: 'scraped',
                    enriched: null,
                    score: c.score ?? null,
                  },
                  tier: event.tier ?? 'high',
                  score: c.score ?? null,
                })
              }
            } else if (event.type === 'ranking') {
              send(event)
            } else if (event.type === 'params') {
              send(event)
            } else if (event.type === 'done') {
              try {
                await prisma.campaign.update({ where: { id }, data: { status: 'scraped' } })
              } catch (e) {
                console.error('[SCRAPE] Erreur mise à jour statut:', e)
              }
              const count = await prisma.company.count({ where: { campaignId: id } })
              console.log('[SCRAPE] done — total DB:', count)
              send({ type: 'done', total: count })
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
