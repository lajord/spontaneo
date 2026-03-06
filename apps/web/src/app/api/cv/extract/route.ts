import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { headers } from 'next/headers'
import { saveCvFile } from '@/lib/file-storage'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL ?? 'http://localhost:8000'

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const formData = await req.formData()

  console.log('[CV EXTRACT] Envoi vers AI service:', `${AI_SERVICE_URL}/api/v1/creation-campagne/extract-cv`)

  try {
    const res = await fetch(`${AI_SERVICE_URL}/api/v1/creation-campagne/extract-cv`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.timeout(120_000),
    })

    console.log('[CV EXTRACT] Réponse AI service:', res.status)

    if (!res.ok) {
      const text = await res.text()
      console.error('[CV EXTRACT] Erreur AI service:', text)
      return NextResponse.json({ error: "Erreur lors de l'extraction du CV" }, { status: 502 })
    }

    const data = await res.json()
    console.log('[CV EXTRACT] Succès, nom extrait:', (data as Record<string, unknown>)?.nom)

    // Sauvegarde du PDF original pour l'attacher aux emails
    let cvFilename: string | null = null
    try {
      const cvFile = formData.get('cv') as File | null
      if (cvFile) {
        const buffer = Buffer.from(await cvFile.arrayBuffer())
        cvFilename = await saveCvFile(session.user.id, buffer)
        console.log('[CV EXTRACT] PDF sauvegardé:', cvFilename)
      }
    } catch (storageErr) {
      // Échec du stockage non bloquant — extraction CV OK quand même
      console.error('[CV EXTRACT] Erreur sauvegarde fichier:', storageErr)
    }

    return NextResponse.json({ ...data, cvFilename })
  } catch (err) {
    console.error('[CV EXTRACT] Exception:', err)
    return NextResponse.json({ error: "Service IA injoignable ou timeout" }, { status: 503 })
  }
}
