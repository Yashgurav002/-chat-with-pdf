# Chat with PDF

A full-stack RAG app that lets you upload a PDF and ask questions about it. Built with FastAPI, LangChain 1.x (LCEL), ChromaDB, and React.

**Live demo:** _Deploy with the steps below, then add your URL here._

---

## What it does

1. Upload a PDF from the browser
2. The backend extracts text, chunks it, embeds it, and stores vectors in an in-memory ChromaDB collection
3. Ask questions in a chat UI — answers stream back token-by-token via Server-Sent Events
4. View the source chunks that grounded each answer

---

## Architecture

```
Browser (React + Vite)
    │
    ├── POST /upload  ──►  PyPDFLoader  ──►  RecursiveCharacterTextSplitter
    │                              │
    │                              ▼
    │                    HuggingFace Embeddings (all-MiniLM-L6-v2)
    │                              │
    │                              ▼
    │                    ChromaDB (in-memory, per session)
    │
    └── POST /chat    ──►  LCEL retrieval chain
                                    │
                    retriever → prompt → Groq LLM → stream tokens
                                    │
                                    ▼
                           SSE response + source chunks
```

### Key design decisions

| Decision | Why |
|---|---|
| **In-memory ChromaDB per session** | Right-sized for a portfolio demo — no Redis, no persistent vector DB, no cost. Trade-off: sessions die when the server restarts or sleeps. |
| **FastEmbed (ONNX) for embeddings** | Free, no API key, ~50 MB RAM — fits Render's 512 MB free tier. PyTorch/sentence-transformers alone exceed the limit. |
| **Groq for LLM (production)** | Free tier, no credit card, extremely fast streaming. Ollama can't run on Render's 512 MB free instances. |
| **LCEL chain (not RetrievalQA)** | LangChain 1.x deprecated the old chain classes. LCEL is composable, debuggable, and streams natively. |
| **SSE via fetch + ReadableStream** | `EventSource` is GET-only. `fetch` + `getReader()` supports POST with a JSON body. |
| **MODE env flag** | Swap Groq ↔ Ollama and HuggingFace ↔ Ollama embeddings for offline local dev without code changes. |

---

## Project structure

```
chat-with-pdf/
├── backend/
│   ├── main.py              # FastAPI routes
│   ├── sessions.py          # In-memory session store
│   ├── rag/
│   │   ├── pipeline.py      # PDF → chunks → Chroma retriever
│   │   └── chain.py         # LCEL retrieval + generation chain
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.jsx
        └── components/
            ├── UploadPanel.jsx
            ├── ChatWindow.jsx
            └── SourceDrawer.jsx
```

---

## Local setup

**Requirements:** Python 3.10+, Node.js 18+

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

App: http://127.0.0.1:5173

### Groq mode (production — default)

Uses HuggingFace `all-MiniLM-L6-v2` embeddings + Groq `llama-3.1-8b-instant`.

1. Get a free API key at [console.groq.com](https://console.groq.com) (GitHub login, no credit card)
2. Set in `backend/.env`:

```
GROQ_API_KEY=your_key_here
MODE=production
```

### Ollama mode (offline local dev)

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

Set in `backend/.env`:

```
MODE=local
OLLAMA_BASE_URL=http://localhost:11434
```

Restart the backend after changing `MODE`.

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes (production mode) | Groq API key from console.groq.com |
| `MODE` | No | `production` (default) or `local` |
| `OLLAMA_BASE_URL` | No | Ollama server URL. Default: `http://localhost:11434` |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | Yes | Backend URL. Local: `http://127.0.0.1:8000` |

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload` | Upload PDF (`multipart/form-data`, field: `file`) → `{ session_id, page_count, chunk_count }` |
| `POST` | `/chat` | `{ session_id, question }` → SSE stream of `{ token }` events, final `{ done, sources }` |
| `DELETE` | `/session/{session_id}` | Clear session → `{ deleted: true }` |
| `GET` | `/health` | Health check → `{ status: "ok" }` |

---

## Deployment

### Backend — Render (free tier, no credit card)

1. Push the repo to GitHub
2. Create a new **Web Service** on [render.com](https://render.com), connect the repo
3. Settings:
   - **Root directory:** `backend`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables in the Render dashboard:
   - `GROQ_API_KEY` = your key
   - `MODE` = `production`
5. After deploy, update CORS in `backend/main.py` — add your Vercel URL to `allow_origins`

### Frontend — Vercel

1. Connect the repo on [vercel.com](https://vercel.com)
2. Settings:
   - **Root directory:** `frontend`
   - **Environment variable:** `VITE_API_BASE_URL` = your Render backend URL (e.g. `https://your-app.onrender.com`)
3. Deploy — Vercel auto-detects Vite

---

## Known limitations

- **In-memory sessions** — uploading a PDF creates a session in a Python dict. Server restart, redeploy, or Render sleep wipes all sessions. Users must re-upload.
- **Render cold starts** — free tier spins down after ~15 min of inactivity. First request after sleep takes ~60 seconds. This is expected, not a bug.
- **First-request model download** — HuggingFace embeddings download ~90 MB on first use. On Render this can timeout. Pre-warm by hitting `/health` after deploy, or add a startup handler that loads the embedding model at boot.
- **Text-layer PDFs only** — `PyPDFLoader` cannot OCR scanned documents.
- **No conversation memory** — each question is independent. Chat history in the UI is cosmetic; the LLM does not see prior turns.
- **No auth or rate limiting** — appropriate for a portfolio demo, not production.

---

## Tech stack

| Layer | Package |
|---|---|
| PDF loading | `langchain-community` → `PyPDFLoader` |
| Chunking | `langchain-text-splitters` → `RecursiveCharacterTextSplitter` (800 / 150) |
| Embeddings | `fastembed` → `BAAI/bge-small-en-v1.5` (ONNX, Render-safe) |
| Vector store | `langchain-chroma` → in-memory ChromaDB |
| LLM | `langchain-groq` → `llama-3.1-8b-instant` |
| Chain | LCEL: `retriever \| prompt \| llm \| StrOutputParser()` |
| Backend | FastAPI + uvicorn |
| Frontend | React + Vite |
