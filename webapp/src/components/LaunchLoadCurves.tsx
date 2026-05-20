import { useMemo } from 'react'

type Point = { freq_hz: number; asd_g2_hz?: number; pv_in_s?: number }

type Props = {
  psd?: Point[]
  srs?: Point[]
}

export function LaunchLoadCurves({ psd, srs }: Props) {
  const psdPath = useMemo(() => pathFromPsd(psd), [psd])
  const srsPath = useMemo(() => pathFromSrs(srs), [srs])

  if (!psdPath && !srsPath) {
    return (
      <p className="muted" style={{ fontSize: '0.78rem' }}>
        Load curves appear after random/shock tests run (bundled MPE or uploaded files).
      </p>
    )
  }

  return (
    <div className="launch-load-curves">
      {psdPath ? (
        <div className="launch-curve-panel">
          <h4 className="launch-section-title">Random PSD (MPE)</h4>
          <svg viewBox="0 0 200 80" className="launch-curve-svg" role="img" aria-label="PSD curve">
            <path d={psdPath} fill="none" stroke="var(--cyan)" strokeWidth="1.5" />
          </svg>
        </div>
      ) : null}
      {srsPath ? (
        <div className="launch-curve-panel">
          <h4 className="launch-section-title">Shock SRS</h4>
          <svg viewBox="0 0 200 80" className="launch-curve-svg" role="img" aria-label="SRS curve">
            <path d={srsPath} fill="none" stroke="var(--accent-orange)" strokeWidth="1.5" />
          </svg>
        </div>
      ) : null}
    </div>
  )
}

function pathFromPsd(pts: Point[] | undefined): string | null {
  if (!pts?.length) return null
  const sorted = [...pts].sort((a, b) => a.freq_hz - b.freq_hz)
  const fmin = Math.log10(Math.max(sorted[0].freq_hz, 1))
  const fmax = Math.log10(sorted[sorted.length - 1].freq_hz)
  const ymax = Math.max(...sorted.map((p) => p.asd_g2_hz ?? 0), 1e-6)
  const coords = sorted.map((p, i) => {
    const x = 10 + ((Math.log10(p.freq_hz) - fmin) / (fmax - fmin || 1)) * 180
    const y = 70 - ((p.asd_g2_hz ?? 0) / ymax) * 60
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  })
  return coords.join(' ')
}

function pathFromSrs(pts: Point[] | undefined): string | null {
  if (!pts?.length) return null
  const sorted = [...pts].sort((a, b) => a.freq_hz - b.freq_hz)
  const fmin = Math.log10(Math.max(sorted[0].freq_hz, 1))
  const fmax = Math.log10(sorted[sorted.length - 1].freq_hz)
  const ymax = Math.max(...sorted.map((p) => p.pv_in_s ?? 0), 1)
  const coords = sorted.map((p, i) => {
    const x = 10 + ((Math.log10(p.freq_hz) - fmin) / (fmax - fmin || 1)) * 180
    const y = 70 - ((p.pv_in_s ?? 0) / ymax) * 60
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  })
  return coords.join(' ')
}
