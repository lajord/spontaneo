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
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildRecipients(enriched: EnrichedData): Recipient[] {
  const recipients: Recipient[] = []
  const usedMails = new Set<string>()

  // Trier par ranking_score décroissant (les contacts les plus pertinents d'abord)
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

  if (recipients.length === 0) {
    recipients.push({
      to: null,
      salutation: 'Bonjour Madame, Monsieur,',
      recipientName: 'Contact générique',
      contactCivilite: null,
      contactPrenom: null,
      contactNom: null,
      contactRole: null,
    })
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

  if (!campaign) {
    throw new Error(`Campaign ${campaignId} not found`)
  }

  // Le status 'running' + startedAt est déjà set par claimNextJob() dans index.ts

  // Determine which companies still need processing
  const alreadyProcessed = await prisma.email.findMany({
    where: { campaignId },
    select: { companyId: true },
    distinct: ['companyId'],
  })
  const processedIds = new Set(alreadyProcessed.map(e => e.companyId))
  const companiesToProcess = campaign.companies.filter(c => !processedIds.has(c.id))

  const cvData = (campaign.cvData ?? {}) as CvData
  const hasLm = !!(campaign.lmText && campaign.lmText.trim().length > 0)
  const customLinks = links.custom ?? []

  // Update total companies count
  await prisma.job.update({
    where: { id: jobId },
    data: { totalCompanies: companiesToProcess.length },
  })

  await prisma.campaign.update({ where: { id: campaignId }, data: { status: 'generating' } })

  const emit = (data: object) => appendJobEvent(jobId, data).catch(err =>
    console.error(`[WORKER] appendJobEvent error:`, err)
  )

  const processCompany = async (company: (typeof campaign.companies)[number]) => {
    // ── 1. Enrichissement ──────────────────────────────────────────────────
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

    // ── 2. Génération du mail ──────────────────────────────────────────────
    await emit({ type: 'generating', companyId: company.id })

    let bodyCore = ''
    let subject = userMailSubject || `Candidature spontanée – ${campaign.jobTitle}`
    // Prendre le contact spécialisé avec le meilleur ranking_score
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

    // ── 3. Destinataires + emails ──────────────────────────────────────────
    const recipients = buildRecipients(enriched)

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
          data: {
            campaignId,
            companyId: company.id,
            subject,
            body: fullBody,
            to: to ?? undefined,
            recipientName,
            status: 'draft',
          },
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
                const updated = await prisma.email.update({
                  where: { id: email.id },
                  data: { generatedLm: lm_adapted },
                })
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
        id: e.id,
        subject: e.subject,
        body: e.body,
        to: e.to ?? null,
        recipientName: e.recipientName ?? null,
        status: e.status,
        generatedLm: e.generatedLm ?? null,
      })),
    })

    // Increment processed count
    await prisma.job.update({
      where: { id: jobId },
      data: { processedCount: { increment: 1 } },
    })
  }

  // ── Traitement parallèle (taille de batch configurable depuis AppConfig) ────
  let batchSize = 3
  try {
    const config = await prisma.appConfig.findUnique({ where: { id: 'singleton' } })
    if (config) batchSize = config.batchSize
  } catch {}
  for (let i = 0; i < companiesToProcess.length; i += batchSize) {
    const batch = companiesToProcess.slice(i, i + batchSize)
    await Promise.all(
      batch.map(company =>
        processCompany(company).catch(err => {
          console.error(`[WORKER] Error processing ${company.name}:`, err)
        })
      )
    )
  }

  await prisma.campaign.update({
    where: { id: campaignId },
    data: { status: 'emails_generated' },
  })

  await emit({ type: 'complete' })

  await prisma.job.update({
    where: { id: jobId },
    data: { status: 'completed', completedAt: new Date() },
  })
}
