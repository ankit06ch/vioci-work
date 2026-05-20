import type { ReactNode } from 'react'

type Size = 'sm' | 'md' | 'lg'

type Props = {
  label?: ReactNode
  size?: Size
  block?: boolean
  className?: string
}

/** Smooth orbital loader — replaces flashing dot pulse. */
export function LoadingIndicator({ label, size = 'sm', block = false, className = '' }: Props) {
  const Tag = block ? 'div' : 'span'
  return (
    <Tag
      className={['loader', `loader--${size}`, block ? 'loader--block' : '', className]
        .filter(Boolean)
        .join(' ')}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="loader-orbit" aria-hidden>
        <span className="loader-orbit-track" />
        <span className="loader-orbit-arc" />
      </span>
      {label ? <span className="loader-label">{label}</span> : null}
    </Tag>
  )
}
