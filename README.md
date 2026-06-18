<div align="center">

# 🗂️ Chat with PDF

### Ask questions across multiple PDFs — with memory, streaming, and source attribution.

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-chat--with--pdf--amber--chi.vercel.app-2E75B6?style=for-the-badge)](https://chat-with-pdf-amber-chi.vercel.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=chainlink&logoColor=white)](https://langchain.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge)](https://www.trychroma.com)

</div>

---

## ✨ What It Does

Upload one or more PDFs and chat with them — the app remembers your previous questions, streams answers token-by-token, and shows you exactly which pages it used to answer.

```
User: "What does the contract say about termination clauses?"
  → Retrieves 4 relevant chunks from 3 uploaded PDFs
  → Streams the answer back live
  → Shows: "Source: contract_v2.pdf — page 14"
```

---

## 🎯 Features

| Feature | How it works |
|---|---|
| 📄 **Multi-PDF upload** | Drag & drop multiple PDFs at once — all land in one shared session |
| 💬 **Conversation memory** | Full chat history passed to the LLM on every turn — follow-ups work naturally |
| ⚡ **Streaming responses** | Token-by-token via SSE — no waiting for the full answer |
| 📍 **Source attribution** | Every answer shows the exact chunk, page number, and filename it came from |
| 🔄 **Local / Cloud mode** | Single `MODE` env flag to switch between Groq (cloud) and Ollama (offline) |

---

## 🏗️ Architecture

```
Browser (React + Vite)
│
├── POST /upload-multiple ──► PyPDFLoader (per file)
│                                    │
│                                    ▼
│                         RecursiveCharacterTextSplitter
│                                    │
│                                    ▼
│                         FastEmbed ONNX Embeddings
│                                    │
│                                    ▼
│                         ChromaDB (in-memory, per session)
│
└── POST /chat ──► LCEL retrieval chain
                          │
              retriever → prompt (+ chat history) → Groq LLM → stream tokens
                          │
                          ▼
               SSE response + source chunks
```

### Key Design Decisions

| Decision | Why |
|---|---|
| **In-memory ChromaDB per session** | Right-sized for a portfolio demo — no Redis, no persistent DB, no cost. Trade-off: sessions clear on server restart. |
| **FastEmbed (ONNX) for embeddings** | Free, no API key, ~50 MB RAM — fits inside Render's 512 MB free tier. PyTorch alone exceeds the limit. |
| **Groq for LLM** | Free tier, no credit card, extremely fast streaming. Ollama can't run on Render's free instances. |
| **LCEL chain (not RetrievalQA)** | LangChain 1.x deprecated old chain classes. LCEL is composable, debuggable, and streams natively. |
| **MessagesPlaceholder for memory** | Chat history injected directly into prompt on every turn — no external memory store needed. |
| **`fetch` + ReadableStream for SSE** | `EventSource` is GET-only. `fetch` + `getReader()` supports POST with a JSON body. |
| **`MODE` env flag** | Swap Groq ↔ Ollama and FastEmbed ↔ Ollama embeddings without touching code. |

---

## 📁 Project Structure

```
chat-with-pdf/
├── backend/
│   ├── main.py              # FastAPI routes (/upload, /upload-multiple, /chat)
│   ├── sessions.py          # In-memory session store (retriever + chat history)
│   ├── rag/
│   │   ├── pipeline.py      # PDF(s) → chunks → Chroma retriever
│   │   └── chain.py         # LCEL chain with conversation memory
│   └── requirements.txt
│
└── frontend/
    └── src/
        ├── App.jsx
        └── components/
            ├── UploadPanel.jsx   # Multi-file dropzone with file pills
            ├── ChatWindow.jsx    # Streaming chat with auto-scroll
            └── SourceDrawer.jsx  # Source chunks with page + filename
```

---

## 🚀 Local Setup

**Requirements:** Python 3.10+ · Node.js 18+

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env     # add your GROQ_API_KEY here
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

> API docs auto-generated at **http://127.0.0.1:8000/docs**

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env     # set VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

> App runs at **http://127.0.0.1:5173**

---

## ⚙️ Modes

### ☁️ Groq Mode (default — production)

Uses **FastEmbed** `BAAI/bge-small-en-v1.5` + **Groq** `llama-3.1-8b-instant`.

1. Get a free key (no credit card) at [console.groq.com](https://console.groq.com)
2. Set in `backend/.env`:

```env
GROQ_API_KEY=your_key_here
MODE=production
```

### 🖥️ Ollama Mode (offline local dev)

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

Set in `backend/.env`:

```env
MODE=local
OLLAMA_BASE_URL=http://localhost:11434
```

Restart the backend after changing `MODE`.

---

## 🌍 Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes (production) | Groq API key from console.groq.com |
| `MODE` | No | `production` (default) or `local` |
| `OLLAMA_BASE_URL` | No | Ollama server URL — default: `http://localhost:11434` |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | Yes | Backend URL — local: `http://127.0.0.1:8000` |

---

## 📡 API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload` | Upload single PDF → `{ session_id, page_count, chunk_count }` |
| `POST` | `/upload-multiple` | Upload multiple PDFs → `{ session_id, doc_count, doc_names, chunk_count }` |
| `POST` | `/chat` | `{ session_id, question }` → SSE stream of `{ token }` events, final `{ done, sources }` |
| `DELETE` | `/session/{session_id}` | Clear session → `{ deleted: true }` |
| `GET` | `/health` | Health check → `{ status: "ok" }` |

---

## 📦 Deployment

### Backend — Render (free tier, no credit card)

1. Push repo to GitHub
2. New **Web Service** on [render.com](https://render.com) → connect repo
3. Settings:
   - **Root directory:** `backend`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in the Render dashboard:
   - `GROQ_API_KEY` = your key
   - `MODE` = `production`
5. Add your Vercel URL to `_cors_origins` in `main.py`

### Frontend — Vercel

1. Connect repo on [vercel.com](https://vercel.com)
2. Settings:
   - **Root directory:** `frontend`
   - **Environment variable:** `VITE_API_BASE_URL` = your Render backend URL
3. Deploy — Vercel auto-detects Vite ✅

---

## ⚠️ Known Limitations

- **In-memory sessions** — sessions live in a Python dict. Server restart or Render sleep wipes all sessions; users must re-upload.
- **Render cold starts** — free tier spins down after ~15 min idle. First request after sleep takes ~60 seconds.
- **512 MB RAM cap** — large PDFs (>1 MB) may OOM on Render's free tier during embedding. Fine for demo-sized docs.
- **10 MB upload cap per file** — enforced in frontend and backend to stay within Render's timeout and RAM limits.
- **Text-layer PDFs only** — `PyPDFLoader` cannot OCR scanned/image-only documents.
- **No auth or rate limiting** — appropriate for a portfolio demo, not production.

---

## 🧰 Tech Stack

| Layer | Library |
|---|---|
| PDF loading | `langchain-community` → `PyPDFLoader` |
| Chunking | `langchain-text-splitters` → `RecursiveCharacterTextSplitter` |
| Embeddings | `fastembed` → `BAAI/bge-small-en-v1.5` (ONNX, Render-safe) |
| Vector store | `langchain-chroma` → in-memory ChromaDB |
| Conversation memory | `langchain-core` → `MessagesPlaceholder` + session-scoped history |
| LLM | `langchain-groq` → `llama-3.1-8b-instant` |
| Chain | LCEL: `RunnableLambda → prompt → llm → StrOutputParser` |
| Backend | FastAPI + uvicorn |
| Frontend | React + Vite + react-markdown |

---

<div align="center">

Built by [your name](https://github.com/yourusername) · Give it a ⭐ if you found it useful!

</div>