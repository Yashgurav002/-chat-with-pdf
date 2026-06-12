import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default function ChatWindow({ sessionId, messages, setMessages, onSources }) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || sending) return

    setInput('')
    setError(null)
    setSending(true)
    onSources([])
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '' },
    ])

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, question }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Chat request failed')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue

          const data = JSON.parse(line.slice(6))
          if (data.error) {
            throw new Error(data.error)
          }
          if (data.token) {
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              next[next.length - 1] = {
                ...last,
                content: last.content + data.token,
              }
              return next
            })
          }
          if (data.done) {
            onSources(data.sources || [])
          }
        }
      }
    } catch (err) {
      const message =
        err.message === 'Failed to fetch' || err.name === 'TypeError'
          ? 'Lost connection to the server. Restart the backend and try again.'
          : err.message || 'Chat request failed'
      setError(message)
      setMessages((prev) => {
        if (prev.at(-1)?.role === 'assistant' && !prev.at(-1)?.content) {
          return prev.slice(0, -1)
        }
        return prev
      })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="chat-window">
      <div className="messages">
        {messages.length === 0 ? (
          <p className="chat-placeholder">Ask a question about your PDF.</p>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`message message-${msg.role}`}>
              <span className="message-role">
                {msg.role === 'user' ? 'You' : 'Assistant'}
              </span>
              <p>{msg.content || (sending && i === messages.length - 1 ? '…' : '')}</p>
            </div>
          ))
        )}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}
    </div>
  )
}
