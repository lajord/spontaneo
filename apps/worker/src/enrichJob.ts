import { prisma, appendJobEvent } from './eventStore'
import { saveLmDocx, saveLmDocxBytes } from './fileStorage'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

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

type Recipient = {
  to: string
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

/**
 * Construit la liste des destinataires a partir des contacts enrichis par l'agent.
 * Lit directement depuis la table AgentContact (liee via AgentCandidate).
 */
async function buildRecipientsFromAgent(
  companyDomain: string | null,
  userId: string,
): Promise<Recipient[]> {
  if (!companyDomain) return []

  const contacts = await prisma.agentContact.findMany({
    where: {
      userId,
      agentCandidate: { domain: companyDomain },
      email: { not: null },
      emailStatus: { in: ['valid', 'catchall'] },
    },
    orderBy: { qualityScore: 'desc' },
  })

  const recipients: Recipient[] = []
  const usedMails = new Set<string>()

  for (const c of contacts) {
    if (!c.email || usedMails.has(c.email)) continue

    const hasName = c.firstName || c.lastName
    if (hasName) {
      const salutation = c.lastName
        ? `Bonjour ${c.lastName.toUpperCase()},`
        : 'Bonjour Madame, Monsieur,'
      recipients.push({
        to: c.email,
        salutation,
        recipientName: [c.firstName, c.lastName].filter(Boolean).join(' ') || c.email,
        contactCivilite: null,
        contactPrenom: c.firstName ?? null,
        contactNom: c.lastName ?? null,
        contactRole: c.title ?? null,
      })
    } else {
      recipients.push({
        to: c.email,
        salutation: 'Bonjour Madame, Monsieur,',
        recipientName: c.name || c.email,
        contactCivilite: null,
        contactPrenom: null,
        contactNom: null,
        contactRole: c.title ?? null,
      })
    }
    usedMails.add(c.email)
  }

  return recipients
}

function normalizeDomain(url?: string | null): string | null {
  if (!url) return null
  let u = url.toLowerCase().trim().replace(/\/$/, '')
  for (const prefix of ['https://www.', 'http://www.', 'https://', 'http://']) {
    if (u.startsWith(prefix)) u = u.slice(prefix.length)
  }
  return u.split('/')[0] || null
}

// ── Core job ──────────────────────────────────────────────────────────────────

export async function runEnrichJob(payload: JobPayload): Promise<void> {
  const { jobId, campaignId, links, userMailTemplate, userMailSubject } = payload

  const campaign = await prisma.campaign.findFirst({
    where: { id: campaignId },
    include: { companies: true, user: { select: { id: true } } },
  })

  if (!campaign) throw new Error(`Campaign ${campaignId} not found`)

  const userId = campaign.userId

  // Determine which companies still need processing
  const alreadyProcessed = await prisma.email.findMany({
    where: { campaignId },
    select: { companyId: true },
    distinct: ['companyId'],
  })
  const processedIds = new Set(alreadyProcessed.map(e => e.companyId))

  let companiesToProcess = campaign.companies.filter(c => !processedIds.has(c.id))

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

  // ── Generation des mails ──────────────────────────────────────────────────

  const generateOne = async (company: (typeof campaign.companies)[number]) => {
    await emit({ type: 'generating', companyId: company.id, companyName: company.name })

    const companyDomain = normalizeDomain(company.website)

    // Recuperer les destinataires depuis AgentContact (enrichis par l'agent)
    const recipients = await buildRecipientsFromAgent(companyDomain, userId)
    const mainContact = recipients[0] ?? null

    let bodyCore = ''
    let subject = userMailSubject || `Candidature spontanee - ${campaign.jobTitle}`

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
            civilite: mainContact.contactCivilite,
            prenom: mainContact.contactPrenom,
            nom: mainContact.contactNom,
            role: mainContact.contactRole,
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
      // Fallback gere ci-dessous
    }

    if (recipients.length === 0) {
      await emit({
        type: 'done',
        companyId: company.id,
        companyName: company.name,
        companyAddress: company.address,
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

        const pitch = bodyCore || `Je vous adresse ce mail comme candidature spontanee pour rejoindre votre entreprise pour un poste de ${campaign.jobTitle}. Je serais ravi(e) d'echanger avec vous a ce sujet.`
        const fullBody = userMailTemplate
          ? [salutation, pitch].filter(Boolean).join('\n\n')
          : [salutation, pitch, attachmentLine, signature].filter(Boolean).join('\n\n')

        const email = await prisma.email.create({
          data: { campaignId, companyId: company.id, subject, body: fullBody, to, recipientName, status: 'draft' },
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
        console.error(`[WORKER] Erreur generation ${c.name}:`, err)
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
