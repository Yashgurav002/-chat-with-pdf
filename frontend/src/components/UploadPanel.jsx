import { useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const MAX_PDF_BYTES = 10 * 1024 * 1024 // 10 MB

export default function UploadPanel({ onUploadSuccess }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  async function uploadFile(file) {
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file.')
      return
    }
    if (file.size > MAX_PDF_BYTES) {
      setError('PDF must be 10 MB or smaller.')
      return
    }

    setUploading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string' ? data.detail : 'Upload failed'
        )
      }
      onUploadSuccess(data)
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function onFileChange(e) {
    uploadFile(e.target.files?.[0])
  }

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    uploadFile(e.dataTransfer.files?.[0])
  }

  return (
    <div className="upload-section">
      <div
        className={`dropzone${dragOver ? ' drag-over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
        }}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={onFileChange}
          hidden
        />
        {uploading ? (
          <p>Processing PDF…</p>
        ) : (
          <>
            <p className="dropzone-title">Drop a PDF here or click to browse</p>
            <p className="dropzone-hint">PDF files only · max 10 MB</p>
          </>
        )}
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
