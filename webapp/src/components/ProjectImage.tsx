import { useEffect, useState, type ImgHTMLAttributes } from 'react'
import { formatApiError, http } from '../api/client'
import { LoadingIndicator } from './LoadingIndicator'

type Props = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  projectId: string
  fallback?: React.ReactNode
}

/** Loads project schematic via authenticated API (browser img src cannot send Bearer). */
export function ProjectImage({ projectId, fallback, alt = '', ...imgProps }: Props) {
  const [src, setSrc] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let revoked = false
    let objectUrl: string | null = null
    setSrc(null)
    setErr(null)

    void (async () => {
      try {
        const { data } = await http.get<Blob>(`/api/projects/${projectId}/image`, {
          responseType: 'blob',
        })
        if (revoked) return
        objectUrl = URL.createObjectURL(data)
        setSrc(objectUrl)
      } catch (e) {
        if (!revoked) setErr(formatApiError(e))
      }
    })()

    return () => {
      revoked = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [projectId])

  if (err) {
    return (
      <div className="project-image-fallback muted" role="status">
        {fallback ?? <span>Image unavailable — {err}</span>}
      </div>
    )
  }

  if (!src) {
    return (
      <LoadingIndicator
        className="project-image-fallback"
        label={fallback ?? 'Loading schematic…'}
        size="md"
        block
      />
    )
  }

  return <img src={src} alt={alt} {...imgProps} />
}
