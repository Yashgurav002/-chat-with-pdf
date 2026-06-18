import { useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const MAX_PDF_BYTES = 10 * 1024 * 1024

export default function UploadPanel({ onUploadSuccess }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState([])

  function validateFiles(files) {
    const valid = []
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError(`${file.name} is not a PDF.`)
        return null
      }
      if (file.size > MAX_PDF_BYTES) {
        setError(`${file.name} exceeds 10 MB limit.`)
        return null
      }
      valid.push(file)
    }
    return valid
  }

  function handleFileChange(e) {
    const files = Array.from(e.target.files || [])
    const valid = validateFiles(files)
    if (valid) {
      setError(null)
      setSelectedFiles(valid)
    }
  }

  function removeFile(index) {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleUpload() {
    if (!selectedFiles.length) return
    setUploading(true)
    setError(null)

    const formData = new FormData()
    selectedFiles.forEach((file) => formData.append('files', file))

    try {
      const res = await fetch(`${API_BASE}/upload-multiple`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Upload failed')
      }
      onUploadSuccess(data)
      setSelectedFiles([])
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files || [])
    const valid = validateFiles(files)
    if (valid) {
      setError(null)
      setSelectedFiles(valid)
    }
  }

  return (
    <div className="upload-section">
      <div
        className={`dropzone${dragOver ? ' drag-over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
          onChange={handleFileChange}
          hidden
        />
        {uploading ? (
          <p>Processing PDFs…</p>
        ) : (
          <>
            <p className="dropzone-title">Drop PDFs here or click to browse</p>
            <p className="dropzone-hint">Multiple PDFs supported · max 10 MB each</p>
          </>
        )}
      </div>

      {selectedFiles.length > 0 && (
        <div className="file-pills">
          {selectedFiles.map((file, i) => (
            <span key={i} className="file-pill">
              {file.name}
              <button
                className="pill-remove"
                onClick={(e) => { e.stopPropagation(); removeFile(i) }}
                aria-label={`Remove ${file.name}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {selectedFiles.length > 0 && !uploading && (
        <button className="upload-btn" onClick={handleUpload}>
          Upload {selectedFiles.length} PDF{selectedFiles.length > 1 ? 's' : ''}
        </button>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  )
}