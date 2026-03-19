import { prisma, appendJobEvent } from './eventStore'
import { saveLmDocx, saveLmDocxBytes } from './fileStorage'
import { verifyEmails } from './neverbounceClient'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'
const NEVER_BOUNCE_API_KEY = process.env.NEVER_BOUNCE_API_KEY ?? ''

// ── Types ─────────────────────────────────────────────────────────────────────

type CvData = {
  nom?: string
  formation?: string[]
  experience?: string[]
  competences_brutes?: string[]
  soft_skills?: string[]
  langues?: string[]
  resume?: string
}

type EnrichedContact = {
  type: 'generique' | 'specialise'
  nom?: string | null
  prenom?: string | null
  role?: string | null
  mail?: string | null
  genre?: 'M' | 'F' | null
  email_verified?: boolean
  phone?: string | null
  linkedin_url?: string | null
  apollo_id?: string | null
  ranking_score?: number | null
}

type EnrichedData = {
  resultats?: EnrichedContact[]
  rankings?: { index: number; score: number; reason: string }[]
}

type Recipient = {
  to: string | null
  salutation: string
  recipientName: string
  contactCivilite: string | null
  contactPrenom: string | null
  contactNom: string | null
  contactRole: string | null
}

export type JobPayload = {
  jobId: string
  campaignId: string
  links: {
    linkedin?: string
    github?: string
    portfolio?: string
    custom?: { label: string; url: string }[]
  }
  userMailTemplate: string | null
  userMailSubject: string | null
  poolLimit: number | null
  autoStart?: boolean
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildRecipients(enriched: EnrichedData): Recipient[] {
  const recipients: Recipient[] = []
  const usedMails = new Set<string>()

  const sorted = [...(enriched.resultats ?? [])].sort((a, b) =>
    (b.ranking_score ?? 0) - (a.ranking_score ?? 0)
  )

  for (const r of sorted) {
    if (!r.mail || usedMails.has(r.mail)) continue

    if (r.type === 'specialise' && (r.nom || r.prenom)) {
      const civilite = r.genre === 'M' ? 'Monsieur' : r.genre === 'F' ? 'Madame' : null
      const salutation = (civilite && r.nom)
        ? `Bonjour ${civilite} ${r.nom.toUpperCase()},`
        : 'Bonjour Madame, Monsieur,'
      const name = [r.prenom, r.nom].filter(Boolean).join(' ')
      recipients.push({
        to: r.mail,
        salutation,
        recipientName: name || r.mail,
        contactCivilite: civilite,
        contactPrenom: r.prenom ?? null,
        contactNom: r.nom ?? null,
        contactRole: r.role ?? null,
      })
    } else {
      recipients.push({
        to: r.mail,
        salutation: 'Bonjour Madame, Monsieur,',
        recipientName: r.mail,
        contactCivilite: null,
        contactPrenom: null,
        contactNom: null,
        contactRole: null,
      })
    }
    usedMails.add(r.mail)
  }

  return recipients
}

// ── Core job ──────────────────────────────────────────────────────────────────

export async function runEnrichJob(payload: JobPayload): Promise<void> {
  const { jobId, campaignId, links, userMailTemplate, userMailSubject } = payload

  const campaign = await prisma.campaign.findFirst({
    where: { id: campaignId },
    include: { companies: true },
  })

  if (!campaign) throw new Error(`Campaign ${campaignId} not found`)

  // Determine which companies still need processing
  const alreadyProcessed = await prisma.email.findMany({
    where: { campaignId },
    select: { companyId: true },
    distinct: ['companyId'],
  })
  const processedIds = new Set(alreadyProcessed.map(e => e.companyId))

  // Sort: Apollo JT first
  const sortedCompanies = [...campaign.companies].sort((a, b) => {
    if (a.source === 'apollo_jobtitle' && b.source !== 'apollo_jobtitle') return -1
    if (b.source === 'apollo_jobtitle' && a.source !== 'apollo_jobtitle') return 1
    return 0
  })

  let companiesToProcess = sortedCompanies.filter(c => !processedIds.has(c.id))

  if (payload.poolLimit && payload.poolLimit > 0) {
    companiesToProcess = companiesToProcess.slice(0, payload.poolLimit)
  }

  const cvData = (campaign.cvData ?? {}) as CvData
  const hasLm = !!(campaign.lmText && campaign.lmText.trim().length > 0)
  const customLinks = links.custom ?? []

  await prisma.job.update({
    where: { id: jobId },
    data: { totalCompanies: companiesToProcess.length },
  })

  await prisma.campaign.update({ where: { id: campaignId }, data: { status: 'generating' } })

  const emit = (data: object) => appendJobEvent(jobId, data).catch(err =>
    console.error(`[WORKER] appendJobEvent error:`, err)
  )

  let batchSize = 3
  try {
    const config = await prisma.appConfig.findUnique({ where: { id: 'singleton' } })
    if (config) batchSize = config.batchSize
  } catch {}

  // ── Phase 1 : Enrichissement de toutes les entreprises ───────────────────

  const enrichedMap = new Map<string, EnrichedData>()

  const enrichOne = async (company: (typeof campaign.companies)[number]) => {
    await emit({ type: 'enriching', companyId: company.id, companyName: company.name })

    let enriched: EnrichedData = {}
    try {
      const isRanked = campaign.enrichMode === 'ranked'
      const enrichEndpoint = isRanked
        ? `${AI_SERVICE_URL}/api/v1/enrichissement/company-ranked`
        : `${AI_SERVICE_URL}/api/v1/enrichissement/company`
      const enrichBody = isRanked
        ? { nom: company.name, site_web: company.website ?? undefined, adresse: company.address ?? undefined, job_title: campaign.jobTitle }
        : { nom: company.name, site_web: company.website ?? undefined, adresse: company.address ?? undefined }

      const enrichRes = await fetch(enrichEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(enrichBody),
        signal: AbortSignal.timeout(20 * 60 * 1000),
      })

      if (enrichRes.ok) {
        enriched = await enrichRes.json()
        await prisma.company.update({
          where: { id: company.id },
          data: { enriched, status: 'enriched' },
        })
      }
    } catch (err) {
      console.error(`[WORKER] Enrichissement échoué pour ${company.name}:`, err)
    }

    enrichedMap.set(company.id, enriched)
    await emit({ type: 'enriched', companyId: company.id, companyName: company.name, enriched })
  }

  for (let i = 0; i < companiesToProcess.length; i += batchSize) {
    const batch = companiesToProcess.slice(i, i + batchSize)
    await Promise.all(
      batch.map(c => enrichOne(c).catch(err => {
        console.error(`[WORKER] Erreur enrichissement ${c.name}:`, err)
        enrichedMap.set(c.id, {})
      }))
    )
  }

  // ── Phase 1.5 : Apollo — récupération des emails manquants ──────────────

  {
    type ApolloItem = {
      ref: string
      first_name?: string
      last_name?: string
      domain?: string
      organization_name?: string
    }

    const apolloItems: ApolloItem[] = []
    const companyById = new Map(companiesToProcess.map(c => [c.id, c]))

    for (const [companyId, enriched] of enrichedMap.entries()) {
      const contacts = enriched.resultats ?? []
      const company = companyById.get(companyId)
      const domain = company?.website
        ? company.website.replace(/^https?:\/\//, '').split('/')[0]
        : undefined

      for (let i = 0; i < contacts.length; i++) {
        const c = contacts[i]
        if (c.type === 'specialise' && !c.mail && (c.nom || c.prenom)) {
          apolloItems.push({
            ref: `${companyId}:${i}`,
            ...(c.prenom ? { first_name: c.prenom } : {}),
            ...(c.nom ? { last_name: c.nom } : {}),
            ...(domain ? { domain } : {}),
            ...(company?.name ? { organization_name: company.name } : {}),
          })
        }
      }
    }

    if (apolloItems.length > 0) {
      await emit({ type: 'apollo_fill_start', total: apolloItems.length })

      const APOLLO_BATCH = 10
      let filled = 0
      const modifiedCompanyIds = new Set<string>()

      for (let i = 0; i < apolloItems.length; i += APOLLO_BATCH) {
        const batch = apolloItems.slice(i, i + APOLLO_BATCH)
        try {
          const res = await fetch(`${AI_SERVICE_URL}/api/v1/apollo/fill-emails`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: batch }),
            signal: AbortSignal.timeout(60_000),
          })

          if (res.ok) {
            const data = await res.json() as {
              results: { ref: string; mail: string | null; email_verified: boolean }[]
            }
            for (const result of data.results) {
              if (!result.mail) continue
              const colonIdx = result.ref.lastIndexOf(':')
              const cId = result.ref.slice(0, colonIdx)
              const contactIdx = parseInt(result.ref.slice(colonIdx + 1), 10)
              const enriched = enrichedMap.get(cId)
              if (enriched?.resultats?.[contactIdx]) {
                enriched.resultats[contactIdx] = { ...enriched.resultats[contactIdx], mail: result.mail }
                filled++
                modifiedCompanyIds.add(cId)
              }
            }
          }
        } catch (err) {
          console.error(`[WORKER] Apollo fill batch ${i}–${i + APOLLO_BATCH} échoué:`, err)
        }
      }

      // Persister les contacts mis à jour en DB
      await Promise.all(
        [...modifiedCompanyIds].map(cId => {
          const enriched = enrichedMap.get(cId)
          if (!enriched) return
          return prisma.company.update({
            where: { id: cId },
            data: { enriched },
          }).catch(err => console.error(`[WORKER] DB update Apollo fill ${cId}:`, err))
        })
      )

      await emit({ type: 'apollo_fill_done', total: apolloItems.length, filled })
    }
  }

  // ── Phase 2 : Vérification NeverBounce ───────────────────────────────────

  if (NEVER_BOUNCE_API_KEY) {
    // Indexer tous les mails uniques → [{companyId, contactIndex}]
    const emailRefs = new Map<string, Array<{ companyId: string; contactIndex: number }>>()

    for (const [companyId, enriched] of enrichedMap.entries()) {
      for (let i = 0; i < (enriched.resultats ?? []).length; i++) {
        const mail = enriched.resultats![i].mail
        if (!mail) continue
        if (!emailRefs.has(mail)) emailRefs.set(mail, [])
        emailRefs.get(mail)!.push({ companyId, contactIndex: i })
      }
    }

    const uniqueEmails = [...emailRefs.keys()]

    if (uniqueEmails.length > 0) {
      await emit({ type: 'verifying_emails', total: uniqueEmails.length })

      const results = await verifyEmails(uniqueEmails, NEVER_BOUNCE_API_KEY)

      let removedCount = 0
      for (const [email, result] of results.entries()) {
        if (result === 'invalid' || result === 'disposable') {
          for (const { companyId, contactIndex } of emailRefs.get(email) ?? []) {
            const enriched = enrichedMap.get(companyId)
            if (enriched?.resultats?.[contactIndex]) {
              enriched.resultats[contactIndex] = { ...enriched.resultats[contactIndex], mail: null }
            }
          }
          removedCount++
        }
      }

      await emit({
        type: 'emails_verified',
        total: uniqueEmails.length,
        valid: uniqueEmails.length - removedCount,
        removed: removedCount,
      })
    }
  }

  // ── Phase 2 : Génération des mails ───────────────────────────────────────

  const generateOne = async (company: (typeof campaign.companies)[number]) => {
    const enriched = enrichedMap.get(company.id) ?? {}

    await emit({ type: 'generating', companyId: company.id, companyName: company.name })

    let bodyCore = ''
    let subject = userMailSubject || `Candidature spontanée – ${campaign.jobTitle}`
    const mainContact = [...(enriched.resultats ?? [])]
      .filter(r => r.type === 'specialise')
      .sort((a, b) => (b.ranking_score ?? 0) - (a.ranking_score ?? 0))[0] ?? null

    try {
      const genRes = await fetch(`${AI_SERVICE_URL}/api/v1/generation-mail/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidat: {
            nom: cvData.nom ?? '',
            formation: cvData.formation ?? [],
            experience: cvData.experience ?? [],
            competences_brutes: cvData.competences_brutes ?? [],
            soft_skills: cvData.soft_skills ?? [],
            langues: cvData.langues ?? [],
            resume: cvData.resume ?? '',
          },
          campagne: {
            jobTitle: campaign.jobTitle,
            location: campaign.location,
            startDate: campaign.startDate ?? null,
            duration: campaign.duration ?? null,
            prompt: campaign.prompt ?? null,
          },
          entreprise: {
            nom: company.name,
            adresse: company.address ?? null,
            site_web: company.website ?? null,
            secteur: company.sector ?? null,
          },
          contact_principal: mainContact ? {
            civilite: mainContact.genre === 'M' ? 'Monsieur' : mainContact.genre === 'F' ? 'Madame' : null,
            prenom: mainContact.prenom ?? null,
            nom: mainContact.nom ?? null,
            role: mainContact.role ?? null,
          } : null,
          user_mail_template: userMailTemplate,
          has_lm: hasLm,
        }),
        signal: AbortSignal.timeout(5 * 60 * 1000),
      })

      if (genRes.ok) {
        const gen = await genRes.json()
        subject = userMailSubject || gen.subject || subject
        bodyCore = gen.body ?? ''
      }
    } catch {
      // Fallback géré ci-dessous
    }

    const recipients = buildRecipients(enriched)

    if (recipients.length === 0) {
      await emit({
        type: 'done',
        companyId: company.id,
        companyName: company.name,
        companyAddress: company.address,
        enriched,
        emails: [],
      })
      await prisma.job.update({ where: { id: jobId }, data: { processedCount: { increment: 1 } } })
      return
    }

    const savedEmails = await Promise.all(
      recipients.map(async (recipient) => {
        const { to, salutation, recipientName } = recipient

        const pjParts = ['mon CV']
        if (hasLm) pjParts.push('ma lettre de motivation')
        const attachmentLine = `Je vous joins ${pjParts.join(' ainsi que ')}.`

        const linksItems = [
          links.linkedin ? `LinkedIn : ${links.linkedin}` : '',
          links.github ? `GitHub : ${links.github}` : '',
          links.portfolio ? `Portfolio : ${links.portfolio}` : '',
          ...customLinks.filter(c => c.label && c.url).map(c => `${c.label} : ${c.url}`),
        ].filter(Boolean)

        const candidatNom = cvData.nom || 'Le candidat'
        const signatureParts = [`Cordialement,\n${candidatNom}`]
        if (linksItems.length > 0) signatureParts.push(linksItems.join('\n'))
        const signature = signatureParts.join('\n')

        const pitch = bodyCore || `Je vous adresse ce mail comme candidature spontanée pour rejoindre votre entreprise pour un poste de ${campaign.jobTitle}. Je serais ravi(e) d'échanger avec vous à ce sujet.`
        const fullBody = userMailTemplate
          ? [salutation, pitch].filter(Boolean).join('\n\n')
          : [salutation, pitch, attachmentLine, signature].filter(Boolean).join('\n\n')

        const email = await prisma.email.create({
          data: { campaignId, companyId: company.id, subject, body: fullBody, to: to ?? undefined, recipientName, status: 'draft' },
        })

        if (campaign.lmText && to) {
          try {
            const lmRes = await fetch(`${AI_SERVICE_URL}/api/v1/generation-lm/generate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                lm_text: campaign.lmText,
                entreprise: { nom: company.name, adresse: company.address ?? null },
                cv_resume: cvData.resume ?? '',
                campaign_prompt: campaign.prompt ?? null,
                destinataire_civilite: recipient.contactCivilite,
                destinataire_prenom: recipient.contactPrenom,
                destinataire_nom: recipient.contactNom,
                destinataire_role: recipient.contactRole,
              }),
              signal: AbortSignal.timeout(5 * 60 * 1000),
            })
            if (lmRes.ok) {
              const { lm_adapted, lm_structured, lm_docx_b64 } = await lmRes.json()
              if (lm_adapted) {
                const updated = await prisma.email.update({ where: { id: email.id }, data: { generatedLm: lm_adapted } })
                if (lm_docx_b64) {
                  saveLmDocxBytes(campaign.userId, email.id, Buffer.from(lm_docx_b64, 'base64')).catch(err =>
                    console.error(`[WORKER] Erreur DOCX bytes LM ${email.id}:`, err)
                  )
                } else {
                  saveLmDocx(campaign.userId, email.id, lm_adapted, lm_structured ?? null).catch(err =>
                    console.error(`[WORKER] Erreur DOCX LM ${email.id}:`, err)
                  )
                }
                return updated
              }
            }
          } catch {
            // LM generation failed — email already saved
          }
        }

        return email
      })
    )

    await emit({
      type: 'done',
      companyId: company.id,
      companyName: company.name,
      companyAddress: company.address,
      enriched,
      emails: savedEmails.map(e => ({
        id: e.id, subject: e.subject, body: e.body,
        to: e.to ?? null, recipientName: e.recipientName ?? null,
        status: e.status, generatedLm: e.generatedLm ?? null,
      })),
    })

    await prisma.job.update({ where: { id: jobId }, data: { processedCount: { increment: 1 } } })
  }

  for (let i = 0; i < companiesToProcess.length; i += batchSize) {
    const batch = companiesToProcess.slice(i, i + batchSize)
    await Promise.all(
      batch.map(c => generateOne(c).catch(err => {
        console.error(`[WORKER] Erreur génération ${c.name}:`, err)
      }))
    )
  }

  // ── Finalisation ─────────────────────────────────────────────────────────

  const freshJob = await prisma.job.findUnique({ where: { id: jobId }, select: { payload: true } })
  const shouldAutoStart = (freshJob?.payload as any)?.autoStart === true
  const totalEmails = await prisma.email.count({ where: { campaignId, status: 'draft' } })

  if (shouldAutoStart && totalEmails > 0) {
    await prisma.campaign.update({
      where: { id: campaignId },
      data: { status: 'active', totalEmails, sentCount: 0, launchedAt: new Date() },
    })
  } else {
    await prisma.campaign.update({ where: { id: campaignId }, data: { status: 'emails_generated' } })
  }

  await emit({ type: 'complete' })

  await prisma.job.update({
    where: { id: jobId },
    data: { status: 'completed', completedAt: new Date() },
  })
}
