import { useCallback, useState } from 'react'

type Props = {
  onFile: (file: File) => void
  label?: string
}

export function SheetUploader({ onFile, label = 'Drop CSV here' }: Props) {
  const [over, setOver] = useState(false)
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setOver(false)
      const f = e.dataTransfer.files[0]
      if (f) onFile(f)
    },
    [onFile],
  )
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`sheet-uploader ${over ? 'sheet-uploader-active' : ''}`}
    >
      {label}
      <div style={{ marginTop: 8 }}>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onFile(f)
          }}
        />
      </div>
    </div>
  )
}
