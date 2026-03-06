import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { headers } from 'next/headers'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const formData = await req.formData()

  console.log('[LM ANALYZE] Envoi vers AI service:', `${AI_SERVICE_URL}/api/v1/creation-campagne/extract-lm`)

  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/v1/creation-campagne/extract-lm`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.timeout(30_000),
    })

    console.log('[LM ANALYZE] Réponse AI service:', res.status)

    if (!res.ok) {
      const text = await res.text()
      console.error('[LM ANALYZE] Erreur AI service:', text)
      return NextResponse.json({ error: "Erreur lors de l'analyse de la lettre de motivation" }, { status: 502 })
    }

    const data = await res.json()
    console.log('[LM ANALYZE] Succès, longueur texte extrait:', (data as Record<string, unknown>)?.lm_text?.toString().length ?? 0)
    return NextResponse.json(data)
  } catch (err) {
    console.error('[LM ANALYZE] Exception:', err)
    return NextResponse.json({ error: "Service IA injoignable ou timeout" }, { status: 503 })
  }
}
