import type { SchemaRegistrySqlResult } from '../api/types'

const SQL_FIRST = new Set(['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH'])

/** True for `sql …` or a statement starting with SELECT/INSERT/UPDATE/DELETE/WITH. */
export function looksLikeRegistrySql(text: string): boolean {
  const t = text.trim()
  if (!t) return false
  if (/^sql\b/i.test(t)) return t.length > 4
  const first = t.split(/\s+/)[0]?.toUpperCase() ?? ''
  return SQL_FIRST.has(first)
}

export function extractSqlFromTerminal(text: string): string {
  const t = text.trim()
  if (/^sql\b/i.test(t)) {
    return t.replace(/^sql\s+/i, '').trim()
  }
  return t
}

export function formatSqlResultForTerminal(res: SchemaRegistrySqlResult): string {
  if (res.message && !res.columns.length) {
    return `${res.message} (${res.row_count} row(s) affected)`
  }
  if (!res.columns.length) {
    return res.mutated
      ? `OK — ${res.row_count} row(s) affected. CSV files updated.`
      : 'OK — no rows returned.'
  }
  const lines: string[] = []
  if (res.mutated) lines.push(`(mutated — ${res.row_count} row(s); registry CSVs updated)`)
  else lines.push(`(${res.row_count} row(s))`)
  const maxRows = 12
  const slice = res.rows.slice(0, maxRows)
  lines.push(res.columns.join('\t'))
  for (const row of slice) {
    lines.push(res.columns.map((c) => String(row[c] ?? '')).join('\t'))
  }
  if (res.rows.length > maxRows) {
    lines.push(`… +${res.rows.length - maxRows} more (see Schema registry tab)`)
  }
  return lines.join('\n')
}
