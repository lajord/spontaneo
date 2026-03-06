import fs from 'fs'
import path from 'path'
import { randomUUID } from 'crypto'
import {
  Document, Paragraph, TextRun, AlignmentType, Packer,
  Table, TableRow, TableCell, WidthType, BorderStyle,
} from 'docx'

export type LmStructured = {
  exp_prenom_nom?: string | null
  exp_adresse?:    string | null
  exp_ville?:      string | null
  exp_telephone?:  string | null
  exp_email?:      string | null
  dest_nom?:       string | null
  dest_service?:   string | null
  dest_adresse?:   string | null
  dest_ville?:     string | null
  date?:           string | null
  objet?:          string | null
  salutation?:     string | null
  corps?:          string | null
  prenom_nom?:     string | null
}

// Racine du dossier de stockage.
// Sur VPS : définir UPLOADS_ROOT en absolu (ex: /srv/spontaneo/uploads)
// En dev local : utilise apps/web/uploads/piece_jointe par défaut
const UPLOADS_ROOT = process.env.UPLOADS_ROOT
  ?? path.join(process.cwd(), 'uploads', 'piece_jointe')

// ── Helpers chemins ───────────────────────────────────────────────────────────

function cvFilePath(userId: string, filename: string): string {
  return path.join(UPLOADS_ROOT, userId, 'cv', filename)
}

function lmFilePath(userId: string, emailId: string): string {
  return path.join(UPLOADS_ROOT, userId, 'lm', `${emailId}.docx`)
}

function extraDir(userId: string, campaignId: string): string {
  return path.join(UPLOADS_ROOT, userId, 'extra', campaignId)
}

// ── Sauvegarde CV ──────────────────────────────────────────────────────────────

/**
 * Sauvegarde le buffer d'un PDF dans le dossier CV de l'utilisateur.
 * Retourne le nom du fichier généré (ex: "a1b2c3.pdf").
 */
export async function saveCvFile(userId: string, buffer: Buffer): Promise<string> {
  const dir = path.join(UPLOADS_ROOT, userId, 'cv')
  fs.mkdirSync(dir, { recursive: true })
  const filename = `${randomUUID()}.pdf`
  fs.writeFileSync(cvFilePath(userId, filename), buffer)
  return filename
}

// ── Génération + sauvegarde LM DOCX ───────────────────────────────────────────

const FONT = 'Times New Roman'
const SIZE = 24 // 12pt en demi-points

function textPara(text: string, align: (typeof AlignmentType)[keyof typeof AlignmentType] = AlignmentType.LEFT): Paragraph {
  return new Paragraph({
    children: [new TextRun({ text, font: FONT, size: SIZE })],
    spacing: { after: text.trim() === '' ? 0 : 160 },
    alignment: align,
  })
}

function blockParagraphs(block: string, align: (typeof AlignmentType)[keyof typeof AlignmentType] = AlignmentType.LEFT): Paragraph[] {
  return block.split(/\r?\n/).map(line => textPara(line, align))
}

const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' } as const
const NO_BORDERS = { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER }

/**
 * Génère un fichier DOCX formaté depuis le texte de la LM personnalisée.
 * Si lmStructured est fourni, construit un en-tête 2 colonnes (format lettre FR).
 * Sauvegarde dans le dossier LM de l'utilisateur sous {emailId}.docx.
 */
export async function saveLmDocx(
  userId: string,
  emailId: string,
  lmText: string,
  lmStructured?: LmStructured | null,
): Promise<void> {
  const dir = path.join(UPLOADS_ROOT, userId, 'lm')
  fs.mkdirSync(dir, { recursive: true })

  const children: (Paragraph | Table)[] = []

  if (lmStructured) {
    const expLines = [
      lmStructured.exp_prenom_nom,
      lmStructured.exp_adresse,
      lmStructured.exp_ville,
      lmStructured.exp_telephone,
      lmStructured.exp_email,
    ].filter(Boolean) as string[]

    const destLines = [
      lmStructured.dest_nom,
      lmStructured.dest_service,
      lmStructured.dest_adresse,
      lmStructured.dest_ville,
    ].filter(Boolean) as string[]

    const expParas  = expLines.length  ? expLines.map(l => textPara(l))  : [textPara('')]
    const destParas = destLines.length ? destLines.map(l => textPara(l, AlignmentType.RIGHT)) : [textPara('')]

    children.push(
      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        borders: { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER },
        rows: [
          new TableRow({
            children: [
              new TableCell({ width: { size: 50, type: WidthType.PERCENTAGE }, borders: NO_BORDERS, children: expParas }),
              new TableCell({ width: { size: 50, type: WidthType.PERCENTAGE }, borders: NO_BORDERS, children: destParas }),
            ],
          }),
        ],
      }),
      textPara(''),
    )

    if (lmStructured.date) {
      children.push(textPara(lmStructured.date, AlignmentType.RIGHT))
      children.push(textPara(''))
    }

    if (lmStructured.objet) {
      children.push(new Paragraph({
        children: [new TextRun({ text: `Objet : ${lmStructured.objet}`, font: FONT, size: SIZE, bold: true })],
        spacing: { after: 160 },
      }))
      children.push(textPara(''))
    }

    if (lmStructured.salutation) {
      children.push(textPara(lmStructured.salutation))
      children.push(textPara(''))
    }

    if (lmStructured.corps) {
      const paras = lmStructured.corps.split(/\n\n+/)
      for (const para of paras) {
        children.push(...blockParagraphs(para))
        children.push(textPara(''))
      }
    }

    if (lmStructured.prenom_nom) {
      children.push(textPara('Cordialement,'))
      children.push(textPara(lmStructured.prenom_nom))
    }

  } else {
    for (const line of lmText.split(/\r?\n/)) {
      children.push(textPara(line))
    }
  }

  const doc = new Document({
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: 1134,
              bottom: 1134,
              left: 1701,
              right: 1134,
            },
          },
        },
        children,
      },
    ],
  })

  const buffer = await Packer.toBuffer(doc)
  fs.writeFileSync(lmFilePath(userId, emailId), buffer)
}

// ── Sauvegarde DOCX bytes bruts (depuis Python) ───────────────────────────────

/**
 * Sauvegarde des bytes DOCX bruts (reçus encodés base64 depuis le service Python).
 */
export async function saveLmDocxBytes(userId: string, emailId: string, buffer: Buffer): Promise<void> {
  const dir = path.join(UPLOADS_ROOT, userId, 'lm')
  fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(lmFilePath(userId, emailId), buffer)
}

// ── Lecture fichiers ───────────────────────────────────────────────────────────

/** Retourne le buffer d'un CV ou null si le fichier n'existe pas. */
export async function readCvFile(userId: string, filename: string): Promise<Buffer | null> {
  const fp = cvFilePath(userId, filename)
  if (!fs.existsSync(fp)) return null
  return fs.readFileSync(fp)
}

/** Retourne le buffer d'une LM DOCX ou null si le fichier n'existe pas. */
export async function readLmFile(userId: string, emailId: string): Promise<Buffer | null> {
  const fp = lmFilePath(userId, emailId)
  if (!fs.existsSync(fp)) return null
  return fs.readFileSync(fp)
}

// ── Pièces jointes supplémentaires ────────────────────────────────────────────

/** Sauvegarde une pièce jointe supplémentaire, retourne le nom de fichier final. */
export async function saveExtraAttachment(
  userId: string,
  campaignId: string,
  originalName: string,
  buffer: Buffer,
): Promise<string> {
  const dir = extraDir(userId, campaignId)
  fs.mkdirSync(dir, { recursive: true })
  const ext = path.extname(originalName) || ''
  const safeName = `${randomUUID()}${ext}`
  fs.writeFileSync(path.join(dir, safeName), buffer)
  fs.writeFileSync(path.join(dir, `${safeName}.meta`), originalName)
  return safeName
}

/** Retourne toutes les pièces jointes supplémentaires d'une campagne. */
export async function readExtraAttachments(
  userId: string,
  campaignId: string,
): Promise<Array<{ name: string; content: Buffer; contentType: string }>> {
  const dir = extraDir(userId, campaignId)
  if (!fs.existsSync(dir)) return []

  const files = fs.readdirSync(dir).filter(f => !f.endsWith('.meta'))
  return files.map(f => {
    const content = fs.readFileSync(path.join(dir, f))
    const metaPath = path.join(dir, `${f}.meta`)
    const originalName = fs.existsSync(metaPath)
      ? fs.readFileSync(metaPath, 'utf8')
      : f
    const ext = path.extname(originalName).toLowerCase()
    const contentType =
      ext === '.pdf' ? 'application/pdf'
        : ext === '.docx' ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
          : 'application/octet-stream'
    return { name: originalName, content, contentType }
  })
}

/** Supprime toutes les pièces jointes supplémentaires d'une campagne. */
export async function deleteExtraAttachments(userId: string, campaignId: string): Promise<void> {
  const dir = extraDir(userId, campaignId)
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true })
}
