import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { headers } from 'next/headers'
import { prisma } from '@/lib/prisma'
import { saveExtraAttachment, deleteExtraAttachments } from '@/lib/file-storage'

export async function POST(
    req: NextRequest,
    { params }: { params: Promise<{ id: string }> },
) {
    const session = await auth.api.getSession({ headers: await headers() })
    if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

    const { id } = await params

    const campaign = await prisma.campaign.findFirst({
        where: { id, userId: session.user.id },
        select: { id: true, userId: true },
    })
    if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

    const formData = await req.formData()
    const files = formData.getAll('files') as File[]

    if (!files.length) return NextResponse.json({ saved: 0 })

    const saved: string[] = []
    for (const file of files) {
        const buffer = Buffer.from(await file.arrayBuffer())
        const name = await saveExtraAttachment(campaign.userId, id, file.name, buffer)
        saved.push(name)
    }

    return NextResponse.json({ saved: saved.length })
}

/** DELETE → supprime toutes les pièces jointes supplémentaires de la campagne */
export async function DELETE(
    _req: NextRequest,
    { params }: { params: Promise<{ id: string }> },
) {
    const session = await auth.api.getSession({ headers: await headers() })
    if (!session) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

    const { id } = await params

    const campaign = await prisma.campaign.findFirst({
        where: { id, userId: session.user.id },
        select: { userId: true },
    })
    if (!campaign) return NextResponse.json({ error: 'Campagne introuvable' }, { status: 404 })

    await deleteExtraAttachments(campaign.userId, id)
    return NextResponse.json({ ok: true })
}
