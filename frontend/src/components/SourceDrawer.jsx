import { useState } from 'react'

export default function SourceDrawer({ sources }) {
  const [open, setOpen] = useState(true)

  if (!sources?.length) return null

  return (
    <div className="source-drawer">
      <button
        type="button"
        className="source-toggle"
        onClick={() => setOpen((v) => !v)}
      >
        Sources ({sources.length}) {open ? '▲' : '▼'}
      </button>

      {open && (
        <ul className="source-list">
          {sources.map((source, i) => (
            <li key={i} className="source-item">
              <span className="source-page">Page {source.page + 1}</span>
              <p>{source.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
