import type { LaunchCompatCheck } from '../api/types'

type Props = {
  tests: LaunchCompatCheck[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function statusClass(s: string): string {
  if (s === 'pass') return 'launch-matrix-pass'
  if (s === 'blocked') return 'launch-matrix-blocked'
  if (s === 'fail') return 'launch-matrix-fail'
  return 'launch-matrix-warn'
}

export function LaunchTestMatrix({ tests, selectedId, onSelect }: Props) {
  if (!tests.length) return null

  return (
    <div className="launch-test-matrix">
      <table className="launch-matrix-table">
        <thead>
          <tr>
            <th>Test</th>
            <th>Status</th>
            <th>Measured</th>
            <th>Limit</th>
            <th>M.S.</th>
          </tr>
        </thead>
        <tbody>
          {tests.map((t) => {
            const st = t.test_status ?? t.status
            const ms = t.margin_of_safety
            return (
              <tr
                key={t.id}
                className={`launch-matrix-row ${selectedId === t.id ? 'launch-matrix-row-active' : ''}`}
                onClick={() => onSelect(t.id)}
              >
                <td>
                  <span className="launch-matrix-cat mono">{t.category}</span>
                  {t.title}
                  {t.mandatory ? <span className="launch-matrix-mand">*</span> : null}
                </td>
                <td>
                  <span className={`launch-matrix-badge ${statusClass(st)}`}>{st}</span>
                </td>
                <td className="mono">{t.value}</td>
                <td className="mono muted">{t.limit}</td>
                <td className="mono">
                  {ms != null ? ms.toFixed(2) : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
