import fs from 'fs'
import path from 'path'
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

// Sur VPS, UPLOADS_ROOT pointe vers le même dossier que la web app.
// Définir la variable en absolu dans .env (ex: /srv/spontaneo/uploads)
// Par défaut pointe vers apps/web/uploads/piece_jointe depuis apps/worker/
const UPLOADS_ROOT = process.env.UPLOADS_ROOT
  ?? path.join(process.cwd(), '..', 'web', 'uploads', 'piece_jointe')

// ── DOCX helpers ──────────────────────────────────────────────────────────────

const FONT = 'Times New Roman'
const SIZE = 24

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

// ── Public functions ──────────────────────────────────────────────────────────

export async function saveLmDocxBytes(userId: string, emailId: string, buffer: Buffer): Promise<void> {
  const dir = path.join(UPLOADS_ROOT, userId, 'lm')
  fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(path.join(dir, `${emailId}.docx`), buffer)
}

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
      lmStructured.exp_prenom_nom, lmStructured.exp_adresse,
      lmStructured.exp_ville, lmStructured.exp_telephone, lmStructured.exp_email,
    ].filter(Boolean) as string[]

    const destLines = [
      lmStructured.dest_nom, lmStructured.dest_service,
      lmStructured.dest_adresse, lmStructured.dest_ville,
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

    if (lmStructured.date)       { children.push(textPara(lmStructured.date, AlignmentType.RIGHT)); children.push(textPara('')) }
    if (lmStructured.objet) {
      children.push(new Paragraph({ children: [new TextRun({ text: `Objet : ${lmStructured.objet}`, font: FONT, size: SIZE, bold: true })], spacing: { after: 160 } }))
      children.push(textPara(''))
    }
    if (lmStructured.salutation) { children.push(textPara(lmStructured.salutation)); children.push(textPara('')) }
    if (lmStructured.corps) {
      for (const para of lmStructured.corps.split(/\n\n+/)) { children.push(...blockParagraphs(para)); children.push(textPara('')) }
    }
    if (lmStructured.prenom_nom) { children.push(textPara('Cordialement,')); children.push(textPara(lmStructured.prenom_nom)) }

  } else {
    for (const line of lmText.split(/\r?\n/)) { children.push(textPara(line)) }
  }

  const doc = new Document({
    sections: [{ properties: { page: { margin: { top: 1134, bottom: 1134, left: 1701, right: 1134 } } }, children }],
  })

  const buffer = await Packer.toBuffer(doc)
  fs.writeFileSync(path.join(dir, `${emailId}.docx`), buffer)
}
