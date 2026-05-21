import { useMemo } from 'react'

type Point = { freq_hz: number; asd_g2_hz?: number; pv_in_s?: number }
type CurvePoint = { x: number; y: number; label: string }
type CurveData = {
  path: string
  points: CurvePoint[]
  minFreq: number
  maxFreq: number
  maxValue: number
  unit: string
}

type Props = {
  psd?: Point[]
  srs?: Point[]
}

export function LaunchLoadCurves({ psd, srs }: Props) {
  const psdCurve = useMemo(() => curveFrom(psd, 'asd_g2_hz', 'g^2/Hz'), [psd])
  const srsCurve = useMemo(() => curveFrom(srs, 'pv_in_s', 'in/s'), [srs])

  if (!psdCurve && !srsCurve) {
    return (
      <p className="muted" style={{ fontSize: '0.78rem' }}>
        Load curves appear after random/shock tests run (bundled MPE or uploaded files).
      </p>
    )
  }

  return (
    <div className="launch-load-curves">
      {psdCurve ? (
        <div className="launch-curve-panel">
          <h4 className="launch-section-title">Random PSD (MPE)</h4>
          <CurveSvg curve={psdCurve} stroke="var(--cyan)" ariaLabel="PSD curve" />
        </div>
      ) : null}
      {srsCurve ? (
        <div className="launch-curve-panel">
          <h4 className="launch-section-title">Shock SRS</h4>
          <CurveSvg curve={srsCurve} stroke="var(--accent-orange)" ariaLabel="SRS curve" />
        </div>
      ) : null}
    </div>
  )
}

function CurveSvg({ curve, stroke, ariaLabel }: { curve: CurveData; stroke: string; ariaLabel: string }) {
  const labelled = curve.points.filter((_, i) => i === 0 || i === curve.points.length - 1 || i % 2 === 1)
  return (
    <svg viewBox="0 0 360 180" className="launch-curve-svg" role="img" aria-label={ariaLabel}>
      <line x1="42" y1="138" x2="332" y2="138" className="launch-curve-axis" />
      <line x1="42" y1="20" x2="42" y2="138" className="launch-curve-axis" />
      <text x="42" y="158" className="launch-curve-tick">
        {curve.minFreq.toFixed(0)} Hz
      </text>
      <text x="286" y="158" className="launch-curve-tick">
        {curve.maxFreq.toFixed(0)} Hz
      </text>
      <text x="48" y="30" className="launch-curve-tick">
        max {curve.maxValue.toFixed(2)} {curve.unit}
      </text>
      <path d={curve.path} fill="none" stroke={stroke} strokeWidth="2.6" />
      {labelled.map((p) => (
        <g key={`${p.x}-${p.y}-${p.label}`}>
          <circle cx={p.x} cy={p.y} r="3.6" fill={stroke} />
          <text x={Math.min(p.x + 6, 300)} y={Math.max(p.y - 6, 18)} className="launch-curve-value-label">
            {p.label}
          </text>
        </g>
      ))}
    </svg>
  )
}

function curveFrom(pts: Point[] | undefined, key: 'asd_g2_hz' | 'pv_in_s', unit: string): CurveData | null {
  if (!pts?.length) return null
  const sorted = [...pts].sort((a, b) => a.freq_hz - b.freq_hz)
  const fmin = Math.log10(Math.max(sorted[0].freq_hz, 1))
  const fmax = Math.log10(sorted[sorted.length - 1].freq_hz)
  const ymax = Math.max(...sorted.map((p) => p[key] ?? 0), key === 'asd_g2_hz' ? 1e-6 : 1)
  const points = sorted.map((p) => {
    const value = p[key] ?? 0
    const x = 42 + ((Math.log10(p.freq_hz) - fmin) / (fmax - fmin || 1)) * 290
    const y = 138 - (value / ymax) * 108
    return {
      x,
      y,
      label: `${p.freq_hz.toFixed(0)}Hz ${value.toFixed(key === 'asd_g2_hz' ? 3 : 1)}`,
    }
  })
  return {
    path: points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' '),
    points,
    minFreq: sorted[0].freq_hz,
    maxFreq: sorted[sorted.length - 1].freq_hz,
    maxValue: ymax,
    unit,
  }
}
