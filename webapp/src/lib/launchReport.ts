import type { LaunchCompatCheck, LaunchCompatResult, LaunchVehicleMeta } from '../api/types'
import type { SatelliteProfile } from './satelliteProfile'

type ReportInput = {
  result: LaunchCompatResult
  tests: LaunchCompatCheck[]
  orbit: string
  profile: SatelliteProfile
  vehicle?: LaunchVehicleMeta
}

export function buildLaunchSuiteLogLines(result: LaunchCompatResult, tests: LaunchCompatCheck[]): string[] {
  const statusSummary = tests.reduce(
    (acc, t) => {
      const s = t.test_status ?? t.status
      acc[s] = (acc[s] ?? 0) + 1
      return acc
    },
    {} as Record<string, number>,
  )

  return [
    `[AEGIS-LV] solver complete engine=${result.engine_version ?? 'launch_physics_v2'} vehicle_rev=${result.vehicle_data_rev ?? 'untracked'}`,
    `[AEGIS-LV] mass=${result.payload_mass_kg.toFixed(2)} kg capacity=${result.capacity_kg.toFixed(0)} kg margin=${result.mass_margin_pct.toFixed(2)}% source=${result.mass_source || 'missing'}`,
    `[AEGIS-LV] status pass=${statusSummary.pass ?? 0} warn=${statusSummary.warn ?? 0} fail=${statusSummary.fail ?? 0} blocked=${statusSummary.blocked ?? 0}`,
    ...tests.map((t, i) => {
      const status = String(t.test_status ?? t.status).toUpperCase()
      const ms = t.margin_of_safety != null ? t.margin_of_safety.toFixed(3) : 'n/a'
      return `[AEGIS-LV] TEST ${String(i + 1).padStart(2, '0')} ${status} ${t.id}: measured=${t.value} limit=${t.limit} MS=${ms} detail=${t.detail}`
    }),
    `[AEGIS-LV] VERDICT ${result.verdict ?? result.overall_status} score=${result.overall_score}%`,
  ]
}

export function buildCheckProgramLogs(
  check: LaunchCompatCheck | null,
  result: LaunchCompatResult | null,
): string[] {
  if (!check) {
    return ['Select a physics simulation test to inspect the execution log.']
  }

  const status = String(check.test_status ?? check.status).toUpperCase()
  const ms = check.margin_of_safety != null ? check.margin_of_safety.toFixed(3) : 'n/a'
  const lines = [
    `program=aegis_lv.${check.category}.${check.id}`,
    `engine=${result?.engine_version ?? 'launch_physics_v2'} vehicle=${result?.vehicle_id ?? 'pending'}`,
    `load inputs: measured=${check.value}; limit=${check.limit}; mandatory=${check.mandatory ? 'true' : 'false'}`,
    `evaluate: status=${status}; margin_of_safety=${ms}`,
    `detail: ${check.detail}`,
  ]

  if (check.assumptions?.length) {
    lines.push(...check.assumptions.map((a) => `assumption: ${a}`))
  }
  if (check.references?.length) {
    lines.push(...check.references.map((r) => `reference: ${r}`))
  }
  if (check.artifacts && Object.keys(check.artifacts).length) {
    lines.push(`artifacts: ${Object.keys(check.artifacts).join(', ')}`)
  }
  return lines
}

export function downloadLaunchReportPdf(input: ReportInput): void {
  const { result, tests, orbit, profile, vehicle } = input
  const pdf = createMissionReportPdf({ result, tests, orbit, profile, vehicle })
  const url = URL.createObjectURL(new Blob([pdf], { type: 'application/pdf' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `aegis-lv-report-${result.vehicle_id}-${Date.now()}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function createMissionReportPdf(input: ReportInput): string {
  const { result, tests, orbit, profile, vehicle } = input
  const statusSummary = tests.reduce(
    (acc, test) => {
      const status = test.test_status ?? test.status
      acc[status] = (acc[status] ?? 0) + 1
      return acc
    },
    {} as Record<string, number>,
  )

  const doc = new MissionPdf()
  const vehicleName = result.vehicle_name ?? vehicle?.name ?? result.vehicle_id
  const verdict = result.verdict ?? result.overall_status

  doc.hero({
    title: 'AEGIS-LV Mission Assurance Report',
    subtitle: `${vehicleName} / ${orbit.toUpperCase()} / ${new Date().toLocaleString()}`,
    verdict,
    score: `${result.overall_score}%`,
  })

  doc.cards([
    { label: 'Verdict', value: verdict, tone: verdict === 'GO' ? 'good' : 'warn' },
    { label: 'Payload', value: `${result.payload_mass_kg.toFixed(0)} kg` },
    { label: 'Capacity', value: `${result.capacity_kg.toFixed(0)} kg` },
    { label: 'Mass Margin', value: `${result.mass_margin_pct.toFixed(1)}%`, tone: result.mass_margin_pct >= 0 ? 'good' : 'bad' },
  ])

  doc.section('Mission Snapshot')
  doc.keyValueGrid([
    ['Vehicle', vehicleName],
    ['Orbit', orbit.toUpperCase()],
    ['Engine', `${result.engine_name ?? 'AEGIS-LV'} ${result.engine_version ?? 'launch_physics_v2'}`],
    ['Vehicle Data Rev', result.vehicle_data_rev ?? 'untracked'],
    ['Mass Source', result.mass_source || 'missing'],
    ['Mission Mass Input', profile.mass_kg != null ? `${profile.mass_kg} kg` : 'n/a'],
  ])

  doc.section('Assurance Summary')
  doc.keyValueGrid([
    ['Pass', String(statusSummary.pass ?? 0)],
    ['Warn', String(statusSummary.warn ?? 0)],
    ['Fail', String(statusSummary.fail ?? 0)],
    ['Blocked', String(statusSummary.blocked ?? 0)],
  ])
  if (result.blockers?.length) {
    doc.callout('Critical Blockers', result.blockers.map((b) => `${b.title}: ${b.detail}`), 'bad')
  } else {
    doc.callout('Critical Blockers', ['No critical blockers reported by the assurance suite.'], 'good')
  }

  const categoryScores = Object.entries(result.category_scores ?? {})
  if (categoryScores.length) {
    doc.section('Category Scores')
    doc.keyValueGrid(categoryScores.map(([category, score]) => [titleCase(category), `${score}%`]))
  }

  doc.section('Suite Log')
  doc.codeBlock(buildLaunchSuiteLogLines(result, tests))

  doc.section('Test Matrix')
  tests.forEach((test, index) => {
    const status = String(test.test_status ?? test.status).toUpperCase()
    const ms = test.margin_of_safety != null ? test.margin_of_safety.toFixed(3) : 'n/a'
    doc.testCard({
      index: index + 1,
      status,
      title: test.title,
      meta: `${test.category} / measured ${test.value} / limit ${test.limit} / MS ${ms}`,
      detail: test.detail,
    })
  })

  doc.section('Detailed Evidence')
  tests.forEach((test) => {
    doc.subsection(test.title)
    doc.codeBlock(buildCheckProgramLogs(test, result))
  })

  return doc.toPdf()
}

type Tone = 'neutral' | 'good' | 'warn' | 'bad'

type SummaryCard = {
  label: string
  value: string
  tone?: Tone
}

type TestCardInput = {
  index: number
  status: string
  title: string
  meta: string
  detail: string
}

const PAGE_WIDTH = 612
const PAGE_HEIGHT = 792
const MARGIN = 42
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2

const COLORS = {
  page: [0.965, 0.975, 0.97],
  ink: [0.08, 0.1, 0.095],
  muted: [0.38, 0.44, 0.42],
  line: [0.78, 0.83, 0.81],
  panel: [0.99, 0.995, 0.99],
  dark: [0.035, 0.065, 0.055],
  dark2: [0.075, 0.12, 0.105],
  accent: [0.29, 0.46, 0.42],
  good: [0.18, 0.44, 0.35],
  warn: [0.58, 0.43, 0.18],
  bad: [0.62, 0.18, 0.18],
}

class MissionPdf {
  private readonly pages: string[][] = []
  private y = PAGE_HEIGHT - MARGIN

  constructor() {
    this.addPage()
  }

  hero(input: { title: string; subtitle: string; verdict: string; score: string }) {
    this.ensure(128)
    this.rect(0, PAGE_HEIGHT - 150, PAGE_WIDTH, 150, COLORS.dark)
    this.rect(0, PAGE_HEIGHT - 150, PAGE_WIDTH, 6, COLORS.accent)
    this.text('VIOCI / LAUNCH COMPATIBILITY', MARGIN, 730, 8.5, 'bold', [0.63, 0.72, 0.69])
    this.text(input.title, MARGIN, 704, 21, 'bold', [0.96, 0.99, 0.98])
    this.text(input.subtitle, MARGIN, 682, 10, 'regular', [0.7, 0.78, 0.75])
    this.badge(input.verdict, 450, 704, toneForStatus(input.verdict))
    this.text(`Score ${input.score}`, 450, 684, 11, 'bold', [0.92, 0.96, 0.94])
    this.y = 612
  }

  cards(cards: SummaryCard[]) {
    const gap = 10
    const width = (CONTENT_WIDTH - gap * (cards.length - 1)) / cards.length
    this.ensure(78)
    cards.forEach((card, i) => {
      const x = MARGIN + i * (width + gap)
      this.rect(x, this.y - 56, width, 56, COLORS.panel, COLORS.line)
      this.text(card.label.toUpperCase(), x + 10, this.y - 18, 7, 'bold', COLORS.muted)
      this.text(card.value, x + 10, this.y - 38, 15, 'bold', colorForTone(card.tone ?? 'neutral'))
    })
    this.y -= 78
  }

  section(title: string) {
    this.ensure(42)
    this.line(MARGIN, this.y, PAGE_WIDTH - MARGIN, this.y, COLORS.line)
    this.text(title.toUpperCase(), MARGIN, this.y - 18, 10, 'bold', COLORS.accent)
    this.y -= 36
  }

  subsection(title: string) {
    this.ensure(28)
    this.text(title, MARGIN, this.y, 10, 'bold', COLORS.ink)
    this.y -= 16
  }

  keyValueGrid(rows: [string, string][]) {
    const colWidth = (CONTENT_WIDTH - 12) / 2
    rows.forEach((row, index) => {
      if (index % 2 === 0) this.ensure(34)
      const x = MARGIN + (index % 2) * (colWidth + 12)
      const y = this.y
      this.rect(x, y - 24, colWidth, 24, [0.985, 0.99, 0.985], COLORS.line)
      this.text(row[0].toUpperCase(), x + 8, y - 9, 6.5, 'bold', COLORS.muted)
      this.text(row[1], x + 8, y - 19, 8.5, 'regular', COLORS.ink, colWidth - 16)
      if (index % 2 === 1 || index === rows.length - 1) this.y -= 32
    })
    this.y -= 8
  }

  callout(title: string, lines: string[], tone: Tone) {
    const wrapped = lines.flatMap((line) => wrapText(line, 82))
    const height = Math.max(46, 28 + wrapped.length * 11)
    this.ensure(height + 8)
    this.rect(MARGIN, this.y - height, CONTENT_WIDTH, height, toneFill(tone), toneStroke(tone))
    this.text(title.toUpperCase(), MARGIN + 12, this.y - 14, 7.5, 'bold', colorForTone(tone))
    wrapped.slice(0, 10).forEach((line, index) => {
      this.text(line, MARGIN + 12, this.y - 30 - index * 11, 8, 'regular', COLORS.ink)
    })
    this.y -= height + 14
  }

  codeBlock(lines: string[]) {
    const wrapped = lines.flatMap((line) => wrapText(line, 96))
    const lineHeight = 10
    let index = 0
    while (index < wrapped.length) {
      const capacity = Math.max(1, Math.floor((this.y - MARGIN - 26) / lineHeight))
      const chunk = wrapped.slice(index, index + capacity)
      const height = 18 + chunk.length * lineHeight
      this.ensure(height)
      this.rect(MARGIN, this.y - height, CONTENT_WIDTH, height, [0.055, 0.08, 0.072])
      chunk.forEach((line, i) => {
        this.text(line, MARGIN + 10, this.y - 14 - i * lineHeight, 7.2, 'mono', [0.78, 0.86, 0.82])
      })
      this.y -= height + 10
      index += chunk.length
    }
  }

  testCard(input: TestCardInput) {
    const detailLines = wrapText(input.detail, 88)
    const height = 58 + Math.min(detailLines.length, 3) * 10
    this.ensure(height + 10)
    this.rect(MARGIN, this.y - height, CONTENT_WIDTH, height, COLORS.panel, COLORS.line)
    this.text(String(input.index).padStart(2, '0'), MARGIN + 10, this.y - 18, 9, 'bold', COLORS.muted)
    this.badge(input.status, MARGIN + 38, this.y - 27, toneForStatus(input.status))
    this.text(input.title, MARGIN + 118, this.y - 18, 10.5, 'bold', COLORS.ink, CONTENT_WIDTH - 128)
    this.text(input.meta, MARGIN + 118, this.y - 32, 7.5, 'regular', COLORS.muted, CONTENT_WIDTH - 128)
    detailLines.slice(0, 3).forEach((line, i) => {
      this.text(line, MARGIN + 118, this.y - 48 - i * 10, 7.8, 'regular', COLORS.ink, CONTENT_WIDTH - 128)
    })
    this.y -= height + 10
  }

  toPdf(): string {
    const pageContents = this.pages.map((ops, index) => {
      const footer = [
        colorOp(COLORS.muted, 'fill'),
        `BT /F1 7 Tf ${MARGIN} 24 Td (${escapePdfText(`AEGIS-LV Mission Assurance / Page ${index + 1}`)}) Tj ET`,
      ]
      return [...ops, ...footer].join('\n')
    })

    const objects: string[] = [
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
      '<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>',
      '',
    ]
  const pageObjectIds: number[] = []

    for (const content of pageContents) {
    const contentId = objects.length + 1
    objects.push(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`)
    const pageId = objects.length + 1
    pageObjectIds.push(pageId)
      objects.push(
        `<< /Type /Page /Parent 4 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] /Resources << /Font << /F1 1 0 R /F2 2 0 R /F3 3 0 R >> >> /Contents ${contentId} 0 R >>`,
      )
  }

  const kids = pageObjectIds.map((id) => `${id} 0 R`).join(' ')
    objects[3] = `<< /Type /Pages /Kids [${kids}] /Count ${pageObjectIds.length} >>`
    objects.push('<< /Type /Catalog /Pages 4 0 R >>')

  const numbered = objects.map((obj, i) => `${i + 1} 0 obj\n${obj}\nendobj\n`)
  let pdf = '%PDF-1.4\n'
  const offsets = [0]
  for (const obj of numbered) {
    offsets.push(pdf.length)
    pdf += obj
  }
  const xref = pdf.length
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
  pdf += offsets
    .slice(1)
    .map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`)
    .join('')
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root ${objects.length} 0 R >>\nstartxref\n${xref}\n%%EOF`
  return pdf
}

  private addPage() {
    this.pages.push([colorOp(COLORS.page, 'fill'), `0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT} re f`])
    this.y = PAGE_HEIGHT - MARGIN
  }

  private ensure(height: number) {
    if (this.y - height < MARGIN) this.addPage()
  }

  private current(): string[] {
    return this.pages[this.pages.length - 1]
  }

  private rect(x: number, y: number, w: number, h: number, fill: number[], stroke?: number[]) {
    this.current().push(colorOp(fill, 'fill'))
    this.current().push(`${fmt(x)} ${fmt(y)} ${fmt(w)} ${fmt(h)} re f`)
    if (stroke) {
      this.current().push(colorOp(stroke, 'stroke'))
      this.current().push(`${fmt(x)} ${fmt(y)} ${fmt(w)} ${fmt(h)} re S`)
    }
  }

  private line(x1: number, y1: number, x2: number, y2: number, color: number[]) {
    this.current().push(colorOp(color, 'stroke'))
    this.current().push(`${fmt(x1)} ${fmt(y1)} m ${fmt(x2)} ${fmt(y2)} l S`)
  }

  private text(
    value: string,
    x: number,
    y: number,
    size: number,
    font: 'regular' | 'bold' | 'mono',
    color: number[],
    maxWidth?: number,
  ) {
    const line = maxWidth ? truncateText(value, Math.floor(maxWidth / (size * 0.5))) : value
    this.current().push(colorOp(color, 'fill'))
    this.current().push(
      `BT /${fontName(font)} ${fmt(size)} Tf ${fmt(x)} ${fmt(y)} Td (${escapePdfText(sanitizePdfText(line))}) Tj ET`,
    )
  }

  private badge(label: string, x: number, y: number, tone: Tone) {
    const text = label.toUpperCase()
    const width = Math.max(54, text.length * 6.5 + 18)
    this.rect(x, y - 14, width, 18, toneFill(tone), toneStroke(tone))
    this.text(text, x + 9, y - 9, 7.5, 'bold', colorForTone(tone))
  }
}

function sanitizePdfText(text: string): string {
  return String(text).replace(/[^\x20-\x7E]/g, ' ')
}

function escapePdfText(text: string): string {
  return text.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

function wrapText(text: string, maxChars: number): string[] {
  const clean = sanitizePdfText(text)
  const words = clean.split(/\s+/)
  const lines: string[] = []
  let line = ''
  for (const word of words) {
    const next = line ? `${line} ${word}` : word
    if (next.length > maxChars && line) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines.length ? lines : ['']
}

function truncateText(text: string, maxChars: number): string {
  const clean = sanitizePdfText(text)
  return clean.length > maxChars ? `${clean.slice(0, Math.max(0, maxChars - 1))}.` : clean
}

function fontName(font: 'regular' | 'bold' | 'mono'): string {
  if (font === 'bold') return 'F2'
  if (font === 'mono') return 'F3'
  return 'F1'
}

function fmt(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

function colorOp(color: number[], target: 'fill' | 'stroke'): string {
  const op = target === 'fill' ? 'rg' : 'RG'
  return `${color.map(fmt).join(' ')} ${op}`
}

function toneForStatus(status: string): Tone {
  const normalized = status.toLowerCase()
  if (normalized === 'go' || normalized === 'pass' || normalized === 'nominal') return 'good'
  if (normalized === 'fail' || normalized === 'blocked' || normalized === 'no-go') return 'bad'
  if (normalized === 'warn' || normalized === 'review' || normalized === 'caution' || normalized === 'conditional') {
    return 'warn'
  }
  return 'neutral'
}

function colorForTone(tone: Tone): number[] {
  if (tone === 'good') return COLORS.good
  if (tone === 'warn') return COLORS.warn
  if (tone === 'bad') return COLORS.bad
  return COLORS.ink
}

function toneFill(tone: Tone): number[] {
  if (tone === 'good') return [0.9, 0.96, 0.93]
  if (tone === 'warn') return [0.98, 0.95, 0.88]
  if (tone === 'bad') return [0.98, 0.91, 0.91]
  return [0.95, 0.97, 0.96]
}

function toneStroke(tone: Tone): number[] {
  if (tone === 'good') return [0.62, 0.78, 0.7]
  if (tone === 'warn') return [0.82, 0.7, 0.46]
  if (tone === 'bad') return [0.84, 0.55, 0.55]
  return COLORS.line
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}
