import { useEffect, useState } from 'react'
import { VIOCI_ICON_SRC } from '../../brand'

const BOOT_LINES = [
  'VIOCI mission integration — boot sequence',
  'Loading operator profile…',
  'Connecting telemetry bus…',
  'Mounting diagram database…',
  'Starting integration terminal…',
  'AI systems online — workspace ready',
]

type Props = {
  onComplete: () => void
}

export function BootSequence({ onComplete }: Props) {
  const [visible, setVisible] = useState(0)
  const [progress, setProgress] = useState(0)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []
    BOOT_LINES.forEach((_, i) => {
      timers.push(
        setTimeout(() => {
          setVisible(i + 1)
          setProgress(Math.round(((i + 1) / BOOT_LINES.length) * 100))
        }, 380 * (i + 1)),
      )
    })
    timers.push(
      setTimeout(() => {
        setExiting(true)
        setTimeout(onComplete, 480)
      }, 380 * BOOT_LINES.length + 400),
    )
    return () => timers.forEach(clearTimeout)
  }, [onComplete])

  return (
    <div className={`boot-overlay ${exiting ? 'exiting' : ''}`}>
      <img src={VIOCI_ICON_SRC} alt="" className="boot-logo vioci-logo" />
      <div className="boot-lines">
        {BOOT_LINES.map((line, i) => (
          <div
            key={line}
            className={`boot-line ${i < visible - 1 ? 'done' : ''} ${i === visible - 1 ? 'active' : ''}`}
            style={{ animationDelay: `${i * 0.08}s` }}
          >
            {i < visible ? `› ${line}` : ''}
          </div>
        ))}
      </div>
      <div className="boot-progress">
        <div className="boot-progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}
