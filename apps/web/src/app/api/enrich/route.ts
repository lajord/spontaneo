import { NextRequest, NextResponse } from 'next/server'

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { secteur, localisation, granularite } = body

    if (!secteur || !localisation) {
      return NextResponse.json({ error: 'Secteur et localisation requis' }, { status: 400 })
    }

    const response = await fetch(`${AI_SERVICE_URL}/api/v1/enrich/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secteur, localisation, granularite: granularite ?? 'moyen' }),
    })

    const data = await response.json()

    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || 'Erreur du service' },
        { status: response.status }
      )
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('Erreur enrich:', error)
    return NextResponse.json({ error: 'Erreur interne' }, { status: 500 })
  }
}
