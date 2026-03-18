import { prisma } from './prisma'

interface EmailConfig {
  id: string
  userId: string
  provider: string
  accessToken: string | null
  refreshToken: string | null
  tokenExpiry: Date | null
  oauthEmail: string | null
}

export interface Attachment {
  name: string
  content: Buffer
  contentType: string
}

interface SendEmailOptions {
  to: string
  subject: string
  body: string
  attachments?: Attachment[]
}

// ── Erreurs custom ────────────────────────────────────────────────────────────

/** Lancée quand le refresh token est révoqué ou expiré — l'utilisateur doit se reconnecter. */
export class OAuthExpiredError extends Error {
  constructor(provider: string) {
    super(`Le token ${provider} a expiré ou a été révoqué. L'utilisateur doit reconnecter son compte email depuis les Paramètres.`)
    this.name = 'OAuthExpiredError'
  }
}

// ── Token refresh ─────────────────────────────────────────────────────────────

async function refreshGmailToken(config: EmailConfig): Promise<string> {
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      refresh_token: config.refreshToken!,
      grant_type: 'refresh_token',
    }),
  })
  const data = await res.json()

  // invalid_grant = refresh token révoqué ou app en mode Test depuis > 7 jours
  if (data.error === 'invalid_grant') {
    throw new OAuthExpiredError('Gmail')
  }
  if (!res.ok) throw new Error(`Gmail token refresh failed: ${data.error_description ?? data.error}`)

  const newExpiry = new Date(Date.now() + data.expires_in * 1000)
  await prisma.emailConfig.update({
    where: { id: config.id },
    data: { accessToken: data.access_token, tokenExpiry: newExpiry },
  })
  return data.access_token as string
}

async function refreshMicrosoftToken(config: EmailConfig): Promise<string> {
  const res = await fetch('https://login.microsoftonline.com/common/oauth2/v2.0/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: process.env.MICROSOFT_CLIENT_ID!,
      client_secret: process.env.MICROSOFT_CLIENT_SECRET!,
      refresh_token: config.refreshToken!,
      grant_type: 'refresh_token',
      scope: 'https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access',
    }),
  })
  const data = await res.json()

  if (data.error === 'invalid_grant') {
    throw new OAuthExpiredError('Microsoft')
  }
  if (!res.ok) throw new Error(`Microsoft token refresh failed: ${data.error_description ?? data.error}`)

  const newExpiry = new Date(Date.now() + data.expires_in * 1000)
  await prisma.emailConfig.update({
    where: { id: config.id },
    data: { accessToken: data.access_token, tokenExpiry: newExpiry },
  })
  return data.access_token as string
}

async function getValidToken(config: EmailConfig, forceRefresh = false): Promise<string> {
  const isExpired = config.tokenExpiry ? config.tokenExpiry.getTime() - Date.now() < 60_000 : true
  console.log(`[email-sender] getValidToken provider=${config.provider} isExpired=${isExpired} forceRefresh=${forceRefresh} tokenExpiry=${config.tokenExpiry?.toISOString()}`)

  if (!forceRefresh && !isExpired && config.accessToken) return config.accessToken

  if (!config.refreshToken) throw new Error('No refresh token available — please reconnect your email account')

  if (config.provider === 'gmail') return refreshGmailToken(config)
  if (config.provider === 'microsoft') return refreshMicrosoftToken(config)
  throw new Error(`Unknown provider: ${config.provider}`)
}

// ── Gmail sending ─────────────────────────────────────────────────────────────

/** Encode un header email non-ASCII en RFC 2047 base64 pour éviter la corruption des accents. */
function encodeRfc2047(value: string): string {
  return `=?UTF-8?B?${Buffer.from(value, 'utf8').toString('base64')}?=`
}

function buildRfc2822(opts: {
  from: string
  to: string
  subject: string
  body: string
  attachments?: Attachment[]
}): string {
  const hasAttachments = (opts.attachments ?? []).length > 0
  const encodedSubject = encodeRfc2047(opts.subject)

  if (!hasAttachments) {
    // Email texte simple
    const message = [
      `From: ${opts.from}`,
      `To: ${opts.to}`,
      `Subject: ${encodedSubject}`,
      'MIME-Version: 1.0',
      'Content-Type: text/plain; charset=UTF-8',
      '',
      opts.body,
    ].join('\r\n')
    return Buffer.from(message).toString('base64url')
  }

  // Email multipart/mixed avec pièces jointes
  const boundary = `----spontaneo_${Date.now()}`
  const parts: string[] = [
    `From: ${opts.from}`,
    `To: ${opts.to}`,
    `Subject: ${encodedSubject}`,
    'MIME-Version: 1.0',
    `Content-Type: multipart/mixed; boundary="${boundary}"`,
    '',
    `--${boundary}`,
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: quoted-printable',
    '',
    opts.body,
  ]

  for (const att of opts.attachments ?? []) {
    parts.push(
      `--${boundary}`,
      `Content-Type: ${att.contentType}; name="${att.name}"`,
      'Content-Transfer-Encoding: base64',
      `Content-Disposition: attachment; filename="${att.name}"`,
      '',
      att.content.toString('base64'),
    )
  }

  parts.push(`--${boundary}--`)
  return Buffer.from(parts.join('\r\n')).toString('base64url')
}

async function sendViaGmail(config: EmailConfig, opts: SendEmailOptions, retried = false): Promise<void> {
  const token = await getValidToken(config, retried)
  const raw = buildRfc2822({
    from: config.oauthEmail!,
    to: opts.to,
    subject: opts.subject,
    body: opts.body,
    attachments: opts.attachments,
  })

  const res = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ raw }),
  })
  const data = await res.json()

  // Si erreur 401 et pas encore réessayé → forcer refresh du token et retry
  if (res.status === 401 && !retried) {
    console.warn('[email-sender] Gmail 401 — forcing token refresh and retrying...')
    return sendViaGmail(config, opts, true)
  }

  if (!res.ok) throw new Error(`Gmail send failed: ${data.error?.message ?? JSON.stringify(data)}`)
}

// ── Microsoft Graph sending ───────────────────────────────────────────────────

async function sendViaMicrosoft(config: EmailConfig, opts: SendEmailOptions, retried = false): Promise<void> {
  const token = await getValidToken(config, retried)

  const attachments = (opts.attachments ?? []).map((att) => ({
    '@odata.type': '#microsoft.graph.fileAttachment',
    name: att.name,
    contentType: att.contentType,
    contentBytes: att.content.toString('base64'),
  }))

  const res = await fetch('https://graph.microsoft.com/v1.0/me/sendMail', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: {
        subject: opts.subject,
        body: { contentType: 'Text', content: opts.body },
        toRecipients: [{ emailAddress: { address: opts.to } }],
        ...(attachments.length > 0 ? { attachments } : {}),
      },
    }),
  })

  if (res.status === 401 && !retried) {
    console.warn('[email-sender] Microsoft 401 — forcing token refresh and retrying...')
    return sendViaMicrosoft(config, opts, true)
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(`Microsoft Graph send failed: ${data.error?.message ?? res.statusText}`)
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function sendEmail(config: EmailConfig, opts: SendEmailOptions): Promise<void> {
  if (config.provider === 'gmail') return sendViaGmail(config, opts)
  if (config.provider === 'microsoft') return sendViaMicrosoft(config, opts)
  throw new Error(`Unsupported email provider: ${config.provider}`)
}
