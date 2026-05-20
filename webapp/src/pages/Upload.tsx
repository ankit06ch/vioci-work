import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadProjects } from '../api/client'

export function Upload() {
  const nav = useNavigate()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  const onFiles = useCallback(
    async (files: FileList | null) => {
      if (!files?.length) return
      setBusy(true)
      setErr(null)
      try {
        await uploadProjects(Array.from(files))
        nav('/')
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e))
      } finally {
        setBusy(false)
      }
    },
    [nav],
  )

  return (
    <div>
      <header className="page-header">
        <h2>Ingest Pipeline</h2>
        <p className="muted">
          Upload schematic assets — each file registers as a new mission workspace
        </p>
      </header>
      <div className="card">
        <div className="panel-head">
          <h3 className="panel-title">
            <span className="panel-icon">↑</span> Asset dropzone
          </h3>
          <span className="hud-chip hud-chip-cyan">READY</span>
        </div>
        <div
          className={`dropzone ${drag ? 'dropzone-active' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDrag(true)
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDrag(false)
            void onFiles(e.dataTransfer.files)
          }}
        >
          <p className="mono" style={{ color: 'var(--cyan)', marginBottom: 8 }}>
            &gt; await ingest_buffer()
          </p>
          <p>{busy ? 'Transmitting to registry…' : 'Drag assets here or select files below.'}</p>
          <input
            type="file"
            multiple
            accept="image/*,.pdf"
            disabled={busy}
            onChange={(e) => void onFiles(e.target.files)}
          />
        </div>
        {err ? <p className="error">{err}</p> : null}
      </div>
    </div>
  )
}
