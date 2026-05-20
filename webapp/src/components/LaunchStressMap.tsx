import { useMemo, useRef, useEffect, useState } from 'react'
import type { LaunchCompatResult } from '../api/types'

type Mode = 'stress' | 'power'

type Props = {
  result: LaunchCompatResult
  mode: Mode
  onModeChange: (m: Mode) => void
}

function stressColor(t: number): string {
  const r = Math.min(255, Math.round(40 + t * 215))
  const g = Math.min(255, Math.round(80 + (1 - t) * 120))
  const b = Math.min(255, Math.round(140 + (1 - t) * 80))
  return `rgb(${r},${g},${b})`
}

function powerColor(t: number): string {
  const r = Math.min(255, Math.round(30 + t * 200))
  const g = Math.min(255, Math.round(60 + t * 100))
  const b = Math.min(255, Math.round(200 - t * 80))
  return `rgb(${r},${g},${b})`
}

export function LaunchStressMap({ result, mode, onModeChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hover, setHover] = useState<{ col: number; row: number; stress: number; power: number } | null>(
    null,
  )
  const sf = result.stress_field
  const grid = mode === 'stress' ? sf.stress_mpa : sf.power_w
  const maxVal = mode === 'stress' ? sf.max_stress_mpa : sf.max_power_w

  const topHotspots = useMemo(
    () => (mode === 'stress' ? sf.hotspots.slice(0, 6) : sf.power_hotspots.slice(0, 6)),
    [mode, sf],
  )

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const w = canvas.width
    const h = canvas.height
    const cw = w / sf.cols
    const ch = h / sf.rows
    ctx.clearRect(0, 0, w, h)
    for (let r = 0; r < sf.rows; r++) {
      for (let c = 0; c < sf.cols; c++) {
        const v = grid[r][c]
        const t = maxVal > 0 ? v / maxVal : 0
        ctx.fillStyle = mode === 'stress' ? stressColor(t) : powerColor(t)
        ctx.fillRect(c * cw, r * ch, cw + 0.5, ch + 0.5)
      }
    }
    const cg = sf.cg
    ctx.strokeStyle = '#00e5ff'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(cg.x * w, cg.y * h, 6, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = '#00e5ff'
    ctx.font = '10px monospace'
    ctx.fillText('CG', cg.x * w + 8, cg.y * h + 4)

    if (hover) {
      ctx.strokeStyle = '#fff'
      ctx.strokeRect(hover.col * cw, hover.row * ch, cw, ch)
    }
  }, [grid, maxVal, mode, sf, hover])

  const onMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    const c = Math.min(sf.cols - 1, Math.max(0, Math.floor(x * sf.cols)))
    const r = Math.min(sf.rows - 1, Math.max(0, Math.floor(y * sf.rows)))
    setHover({
      col: c,
      row: r,
      stress: sf.stress_mpa[r][c],
      power: sf.power_w[r][c],
    })
  }

  return (
    <div className="launch-stress-map">
      <div className="launch-stress-map-head">
        <div className="launch-stress-toggle">
          <button
            type="button"
            className={mode === 'stress' ? 'launch-stress-toggle-active' : ''}
            onClick={() => onModeChange('stress')}
          >
            Structural stress
          </button>
          <button
            type="button"
            className={mode === 'power' ? 'launch-stress-toggle-active' : ''}
            onClick={() => onModeChange('power')}
          >
            Power density
          </button>
        </div>
        <span className="muted mono" style={{ fontSize: '0.72rem' }}>
          {mode === 'stress'
            ? `Peak ${sf.max_stress_mpa.toFixed(2)} MPa (surrogate FEA)`
            : `Peak ${sf.max_power_w.toFixed(1)} W`}
          {' · '}
          1st bend ≈ {sf.first_bending_hz} Hz
        </span>
      </div>

      <div className="launch-stress-canvas-wrap">
        <canvas
          ref={canvasRef}
          width={480}
          height={320}
          className="launch-stress-canvas"
          onMouseMove={onMouseMove}
          onMouseLeave={() => setHover(null)}
        />
        <div className="launch-stress-legend">
          <span>Low</span>
          <div className="launch-stress-legend-bar" data-mode={mode} />
          <span>High</span>
        </div>
      </div>

      {hover ? (
        <p className="launch-stress-hover mono">
          Cell ({hover.col}, {hover.row}) — stress {hover.stress.toFixed(3)} MPa · power{' '}
          {hover.power.toFixed(1)} W
        </p>
      ) : null}

      <div className="launch-hotspots">
        <h4 className="launch-section-title">
          {mode === 'stress' ? 'Peak stress on bus frame' : 'Peak power placement'}
        </h4>
        <ul className="launch-hotspot-list">
          {topHotspots.map((h, i) => (
            <li key={`${h.col}-${h.row}-${i}`}>
              <span className="mono launch-hotspot-rank">#{i + 1}</span>
              <span>
                ({Math.round(h.x * 100)}%, {Math.round(h.y * 100)}%)
              </span>
              <span className="mono">
                {mode === 'stress' ? `${h.stress_mpa.toFixed(2)} MPa` : `${h.power_w.toFixed(1)} W`}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
