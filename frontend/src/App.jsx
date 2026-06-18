import { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import SourceDrawer from './components/SourceDrawer'
import UploadPanel from './components/UploadPanel'
import './App.css'

function App() {
  const [session, setSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [sources, setSources] = useState([])

  function handleUploadSuccess(data) {
    setSession(data)
    setMessages([])
    setSources([])
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Chat with PDF</h1>
        <p>Upload one or more PDFs to start asking questions.</p>
      </header>

      <UploadPanel onUploadSuccess={handleUploadSuccess} />

      {session && (
        <>
          <div className="session-info">
            <span className="ready-badge">Ready to chat</span>
            <span className="stats-badge">
              {session.doc_count
                ? `${session.doc_count} docs · ${session.page_count} pages · ${session.chunk_count} chunks`
                : `${session.page_count} pages · ${session.chunk_count} chunks`}
            </span>
          </div>

          {session.doc_names && session.doc_names.length > 0 && (
            <div className="doc-names">
              {session.doc_names.map((name, i) => (
                <span key={i} className="doc-name-badge">{name}</span>
              ))}
            </div>
          )}

          <ChatWindow
            sessionId={session.session_id}
            messages={messages}
            setMessages={setMessages}
            onSources={setSources}
          />

          <SourceDrawer sources={sources} />
        </>
      )}
    </div>
  )
}

export default App