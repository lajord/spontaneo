import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'

async function requireAdmin() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) return null
  if ((session.user as any).role !== 'admin') return null
  return session
}

// Upsert singleton — retourne la config existante ou en cree une avec les defauts
async function getOrCreateConfig() {
  return prisma.appConfig.upsert({
    where: { id: 'singleton' },
    update: {},
    create: { id: 'singleton' },
  })
}

export async function GET() {
  const session = await requireAdmin()
  if (!session) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const config = await getOrCreateConfig()
  return NextResponse.json(config)
}

export async function PATCH(request: NextRequest) {
  const session = await requireAdmin()
  if (!session) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const body = await request.json()
  const {
    maxConcurrent, batchSize, pollIntervalMs,
    modelEnrichissement, modelEnrichissement2,
    modelCreationMail, modelCreationLm,
    modelKeywords, modelCvReader, modelRanking,
  } = body

  // Validation
  const errors: string[] = []
  if (maxConcurrent !== undefined) {
    if (!Number.isInteger(maxConcurrent) || maxConcurrent < 1 || maxConcurrent > 10) {
      errors.push('maxConcurrent doit etre entre 1 et 10')
    }
  }
  if (batchSize !== undefined) {
    if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 20) {
      errors.push('batchSize doit etre entre 1 et 20')
    }
  }
  if (pollIntervalMs !== undefined) {
    if (!Number.isInteger(pollIntervalMs) || pollIntervalMs < 5000 || pollIntervalMs > 120000) {
      errors.push('pollIntervalMs doit etre entre 5000 et 120000')
    }
  }

  // Validate model strings (non-empty if provided)
  const modelFields = {
    modelEnrichissement, modelEnrichissement2,
    modelCreationMail, modelCreationLm,
    modelKeywords, modelCvReader, modelRanking,
  }
  for (const [key, val] of Object.entries(modelFields)) {
    if (val !== undefined && (typeof val !== 'string' || val.trim().length === 0)) {
      errors.push(`${key} doit etre une chaine non vide`)
    }
  }

  if (errors.length > 0) {
    return NextResponse.json({ errors }, { status: 400 })
  }

  // Build update data with only provided fields
  const data: Record<string, number | string> = {}
  if (maxConcurrent !== undefined) data.maxConcurrent = maxConcurrent
  if (batchSize !== undefined) data.batchSize = batchSize
  if (pollIntervalMs !== undefined) data.pollIntervalMs = pollIntervalMs
  for (const [key, val] of Object.entries(modelFields)) {
    if (val !== undefined) data[key] = (val as string).trim()
  }

  const config = await prisma.appConfig.upsert({
    where: { id: 'singleton' },
    update: data,
    create: { id: 'singleton', ...data },
  })

  return NextResponse.json(config)
}
