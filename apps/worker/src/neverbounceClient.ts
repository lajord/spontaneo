const NB_BASE_URL = 'https://api.neverbounce.com/v4'

export type NeverBounceResult = 'valid' | 'invalid' | 'catchall' | 'disposable' | 'unknown'

export async function verifyEmail(email: string, apiKey: string): Promise<NeverBounceResult> {
  try {
    const url = `${NB_BASE_URL}/single/check?key=${encodeURIComponent(apiKey)}&email=${encodeURIComponent(email)}&timeout=30`
    const res = await fetch(url, { signal: AbortSignal.timeout(35_000) })
    if (!res.ok) return 'unknown'
    const data = await res.json()
    if (data.status === 'success') return data.result as NeverBounceResult
    return 'unknown'
  } catch {
    return 'unknown'
  }
}

export async function verifyEmails(
  emails: string[],
  apiKey: string,
  concurrency = 5,
): Promise<Map<string, NeverBounceResult>> {
  const results = new Map<string, NeverBounceResult>()

  for (let i = 0; i < emails.length; i += concurrency) {
    const batch = emails.slice(i, i + concurrency)
    const batchResults = await Promise.all(
      batch.map(async email => ({ email, result: await verifyEmail(email, apiKey) }))
    )
    for (const { email, result } of batchResults) {
      results.set(email, result)
    }
  }

  return results
}
