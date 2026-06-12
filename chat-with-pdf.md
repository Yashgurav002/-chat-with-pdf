# PRD: Chat with Any PDF

## Problem Statement

Developers need a portfolio-worthy, full-stack AI project that demonstrates real production
thinking — not just a Jupyter notebook demo. The specific gap is a publicly deployable
"Chat with PDF" app that uses a proper RAG pipeline (upload → embed → retrieve → answer)
with a clean React frontend, a FastAPI backend, and a free hosting setup that works without
a credit card. The project must use non-deprecated, actively maintained library versions and
be explainable confidently in a technical interview.

---

## Solution

A two-repo (or monorepo with two root-level folders) web application:

- **Backend**: FastAPI + LangChain v1.x (LCEL) + ChromaDB + HuggingFace embeddings +
  Groq-hosted LLM (free tier, no local Ollama dependency needed on the server).
- **Frontend**: React (Vite) with a minimal but professional UI — file upload, chat
  interface, source-chunk display.
- **Deployment**: Backend on Render free tier (no credit card required), frontend on Vercel.

### Why not Ollama on the server?

Ollama is a local-first tool — it runs a model server process. Free cloud hosts like Render
and Koyeb give you 512 MB RAM and 0.1–0.5 vCPU. Running any LLM locally in that environment
is not viable. The correct architecture for a free deployment is:

- **Embeddings**: `all-MiniLM-L6-v2` via `langchain-huggingface` — runs on CPU in ~100 MB.
  No API key needed, completely free.
- **LLM inference**: [Groq](https://console.groq.com) free tier via `langchain-groq`.
  Groq's free tier gives 14,400 requests/day on Llama-3-8b with no credit card required.
  Latency is extremely fast (token streaming feels instant).

This means Ollama is still the right tool for **local development** (swap in `ChatOllama`
and `OllamaEmbeddings` from `langchain-ollama` when running on your machine), and Groq +
HuggingFace handles production. The README should document both modes — this is actually a
better resume story than "works only locally".

---

## User Stories

1. As a user, I want to upload a PDF file from my browser, so that I can ask questions about it.
2. As a user, I want to see a loading indicator while my PDF is being processed, so that I know the system is working.
3. As a user, I want to type a question in a chat input and receive an answer grounded in the PDF, so that I can extract information without reading the whole document.
4. As a user, I want to see which chunks of the PDF were used to generate the answer, so that I can verify the source.
5. As a user, I want to ask follow-up questions in the same session without re-uploading the PDF, so that I can have a natural conversation.
6. As a user, I want to upload a new PDF and start a fresh session, so that I can switch documents mid-session.
7. As a user, I want to see a clear error message if the upload fails or the file is not a valid PDF, so that I know what went wrong.
8. As a user, I want the app to work on mobile browsers with a readable layout, so that I can use it from any device.
9. As a developer, I want a documented `.env.example` file, so that I can run the project locally in under 5 minutes.
10. As a developer, I want the README to explain the full RAG architecture, so that I can explain the project in a technical interview.
11. As a developer, I want a local-mode flag that swaps Groq for Ollama, so that I can develop offline without burning API quota.
12. As a recruiter or interviewer, I want to click a live URL and interact with the deployed app, so that I can evaluate the candidate's work without setup.

---

## Implementation Decisions

### Tech Stack (canonical, non-deprecated versions as of June 2026)

| Layer | Package | Notes |
|---|---|---|
| PDF loading | `langchain-community` → `PyPDFLoader` | Stable. For scanned/complex PDFs, `UnstructuredPDFLoader` is the upgrade path |
| Text splitting | `langchain-text-splitters` → `RecursiveCharacterTextSplitter` | Chunk size 800, overlap 150 — good starting defaults |
| Embeddings (prod) | `langchain-huggingface` → `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")` | Free, CPU-friendly, 384-dim vectors |
| Embeddings (local) | `langchain-ollama` → `OllamaEmbeddings(model="nomic-embed-text")` | Swap via env flag |
| Vector store | `langchain-chroma` → `Chroma` | Per-session in-memory; no persistence needed for this scope |
| LLM (prod) | `langchain-groq` → `ChatGroq(model="llama-3-8b-8192")` | Free tier, fast, no credit card |
| LLM (local) | `langchain-ollama` → `ChatOllama(model="llama3.2")` | Swap via env flag |
| Chain pattern | LCEL: `retriever \| prompt \| llm \| StrOutputParser()` | `LLMChain` / `RetrievalQA` are deprecated in LangChain 1.x — do not use |
| Backend framework | `FastAPI` + `uvicorn` | |
| Backend hosting | **Render** free tier (no credit card) | Cold start ~60s after inactivity — acceptable for portfolio |
| Frontend framework | React + Vite | |
| Frontend hosting | Vercel | |

**Deprecated patterns to avoid (LangChain 1.x):**
- `LLMChain` — replaced by LCEL pipe syntax
- `SequentialChain` — replaced by LCEL
- `ConversationChain` — replaced by LCEL + `RunnableWithMessageHistory`
- `RetrievalQA` — replaced by LCEL retrieval chain
- `from langchain.chat_models import ChatOpenAI` — use package-specific imports like `from langchain_groq import ChatGroq`
- `from langchain.vectorstores import Chroma` — use `from langchain_chroma import Chroma`

### Session Architecture

ChromaDB will be used **in-memory, per-upload**. Each time a user uploads a PDF, the
backend creates a new in-memory Chroma collection, embeds the chunks, and stores a
`session_id` → `retriever` mapping in a Python dict. This is intentionally simple — no
Redis, no database, no persistent disk. The session dict lives as long as the server
process is alive. For a portfolio project with one or two concurrent users, this is correct.

Session ID is a UUID generated at upload time and returned to the frontend. All subsequent
`/chat` requests include this session ID so the backend knows which retriever to use.

### API Contract

**POST /upload**
- Body: `multipart/form-data` with field `file` (PDF)
- Response: `{ "session_id": "<uuid>", "page_count": <int>, "chunk_count": <int> }`

**POST /chat**
- Body: `{ "session_id": "<uuid>", "question": "<string>" }`
- Response (streaming): Server-Sent Events, each event is `{ "token": "<string>" }`, final event is `{ "done": true, "sources": [{ "page": <int>, "text": "<string>" }] }`

**DELETE /session/{session_id}**
- Clears the in-memory retriever for that session
- Response: `{ "deleted": true }`

### CORS

Backend must allow requests from the Vercel frontend domain and `localhost:5173` during
development. Use FastAPI's `CORSMiddleware`.

### Frontend Architecture

Three components:

- `UploadPanel` — drag-and-drop + file input, shows processing state, stores `session_id`
  in React state (not localStorage)
- `ChatWindow` — message list, streaming token rendering
- `SourceDrawer` — shows retrieved chunks after each answer

State lives in the root `App` component and is passed down as props. No Redux, no context
needed at this scale.

### Environment Variables

```
# .env (backend)
GROQ_API_KEY=<from console.groq.com>
MODE=production          # or "local" to swap to Ollama
OLLAMA_BASE_URL=http://localhost:11434   # only used when MODE=local
```

```
# .env (frontend)
VITE_API_BASE_URL=https://your-backend.onrender.com
```

---

## Step-by-Step Implementation Plan

### Phase 1: Repo & Environment Setup

1. Create a GitHub repo named `chat-with-pdf`. Add a root-level `README.md` (placeholder),
   `.gitignore` covering `__pycache__`, `.env`, `chroma_data/`, `node_modules/`, `dist/`.
   Create two folders: `backend/` and `frontend/`.

2. Inside `backend/`, create `requirements.txt` with:
   ```
   fastapi
   uvicorn[standard]
   python-multipart
   langchain
   langchain-community
   langchain-text-splitters
   langchain-huggingface
   langchain-chroma
   langchain-groq
   langchain-ollama
   chromadb
   pypdf
   sentence-transformers
   ```
   Create `.env.example`. Verify you're on **Python 3.10+** (LangChain 1.x dropped 3.9).

3. Create the React app inside `frontend/` using `npm create vite@latest . -- --template react`.
   Install no extra UI libraries yet — keep it dependency-light for Vercel build speed.

4. Get a Groq API key from `console.groq.com` (GitHub login, no credit card). Add to `.env`.

**Verify before moving on**: `uvicorn main:app --reload` starts without errors, and `npm run dev` loads a blank Vite page.

---

### Phase 2: Backend — Ingestion Pipeline

5. Create `backend/rag/pipeline.py`. Define a `build_retriever(pdf_bytes: bytes) -> VectorStoreRetriever` function:
   - Write `pdf_bytes` to a temp file using Python's `tempfile` module
   - Load with `PyPDFLoader(tmp_path).load()`
   - Split with `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`
   - Choose embedding model based on `MODE` env var:
     - `production` → `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")`
     - `local` → `OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)`
   - Store in `Chroma(collection_name=session_id, embedding_function=embeddings)` — no `persist_directory`, so it's in-memory
   - Return `vectorstore.as_retriever(search_kwargs={"k": 4})`

   **Pitfall**: `filter_complex_metadata=True` should be passed to `text_splitter.split_documents()` to strip ChromaDB-incompatible metadata. Without this, ChromaDB will throw on PDFs with complex metadata.

   **Verify**: Write a quick standalone script that loads a sample PDF and prints retrieved chunks.

---

### Phase 3: Backend — Chain & Session Management

6. Create `backend/rag/chain.py`. Define `build_chain(retriever)` using LCEL:

   ```python
   # Pseudocode — encode the decision, not the exact implementation
   prompt = ChatPromptTemplate.from_messages([
       ("system", "Answer only from the provided context. If you don't know, say so.\n\nContext:\n{context}"),
       ("human", "{question}"),
   ])
   
   chain = (
       {"context": retriever | format_docs, "question": RunnablePassthrough()}
       | prompt
       | llm
       | StrOutputParser()
   )
   ```
   
   Do NOT use `RetrievalQA.from_chain_type()` — it is deprecated. The LCEL pattern above is
   the LangChain 1.x canonical approach.

7. Create `backend/sessions.py`. A plain Python dict `SESSION_STORE: dict[str, dict]`
   where each value holds the retriever and chunk list for source attribution. This dict
   is module-level and lives in memory for the process lifetime.

   **Pitfall**: Free Render instances restart on deploy and sleep after inactivity. Sleeping
   wipes the in-memory dict. This is expected and should be documented in the README —
   users will need to re-upload after the server sleeps.

---

### Phase 4: Backend — FastAPI Routes

8. Create `backend/main.py`:
   - Mount `CORSMiddleware` allowing `["*"]` origins for development (tighten to your
     Vercel URL before final deploy)
   - `POST /upload` — receives the file, calls `build_retriever()`, stores in
     `SESSION_STORE`, returns `session_id` + stats
   - `POST /chat` — looks up session, calls `chain.astream()`, streams tokens back as
     Server-Sent Events using FastAPI's `StreamingResponse`
   - `DELETE /session/{session_id}` — removes from `SESSION_STORE`

   **Pitfall**: SSE in FastAPI requires `StreamingResponse` with `media_type="text/event-stream"`.
   Each yielded string must be in the SSE format: `data: <json>\n\n`. Missing the double
   newline will cause the browser EventSource to silently fail.

   **Verify**: Test all three endpoints with `curl` or the auto-generated Swagger UI at
   `/docs` before touching the frontend.

---

### Phase 5: Frontend — Upload + Session Flow

9. Build `UploadPanel.jsx`:
   - `<input type="file" accept=".pdf" />` wrapped in a drag-and-drop zone (native HTML,
     no library needed)
   - On file select, `POST /upload` with `FormData`
   - On success, lift `session_id` up to `App` state
   - Show chunk count and page count in a small info badge

   **Verify**: After upload, `session_id` is stored in React state and a "Ready to chat"
   state is visible.

---

### Phase 6: Frontend — Chat Interface

10. Build `ChatWindow.jsx`:
    - Message list rendered from `messages` state array (each item: `{role, content}`)
    - On send, `POST /chat`, read the SSE stream using the Fetch API's `ReadableStream`
      (not EventSource, because EventSource is GET-only — use `fetch` + `response.body.getReader()`)
    - Append tokens to the current assistant message as they stream in
    - After the stream ends, parse the final `done: true` event to extract `sources`

11. Build `SourceDrawer.jsx`:
    - A collapsible panel that appears after each answer
    - Lists each retrieved chunk with its page number
    - Toggle open/close — a simple `useState` boolean

    **Verify**: Ask a question, watch tokens stream in real time, collapse/expand sources.

---

### Phase 7: README + Repo Polish

12. Write a `README.md` that covers:
    - What the project does and a live demo link
    - Architecture diagram (even a text-based one showing: PDF → PyPDFLoader → Chunker →
      HuggingFace Embeddings → ChromaDB → LCEL Retrieval Chain → Groq Llama-3)
    - Local setup instructions (with Ollama mode and Groq mode)
    - Environment variables reference
    - Deployment guide for Render + Vercel
    - Known limitations (in-memory sessions, cold start latency)

    This README is the first thing a recruiter or interviewer reads — it should explain
    your architectural decisions, not just list setup steps.

---

### Phase 8: Deployment

13. **Backend on Render**:
    - Create a new Web Service on [render.com](https://render.com), connect the GitHub repo,
      set root directory to `backend/`
    - Build command: `pip install -r requirements.txt`
    - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
    - Set env vars (`GROQ_API_KEY`, `MODE=production`) in the Render dashboard
    - **Note on cold starts**: Render free tier spins down after 15 minutes of inactivity.
      The first request takes ~60 seconds to wake. This is a known limitation — document it
      in the README so interviewers don't think it's a bug.
    - **Potential issue**: The first time `HuggingFaceEmbeddings` runs, it downloads the
      model (~90 MB). This can time out on the first request. Fix: add a `@app.on_event("startup")`
      handler that initializes the embedding model once when the server starts, so it's
      cached in memory.

14. **Frontend on Vercel**:
    - Connect the repo to Vercel, set root directory to `frontend/`
    - Set `VITE_API_BASE_URL` to your Render backend URL
    - Vercel auto-detects Vite and deploys on every push to `main`

    **Final verify**: Upload a PDF on the live URL, ask a question, see tokens stream.

---

## Testing Decisions

A good test for this project tests observable behavior, not implementation internals.
Do not test private functions or the internal structure of the session store — test
what the API actually returns.

**Modules to test:**

- `rag/pipeline.py` — Integration test: feed in a real PDF's bytes, assert the returned
  retriever can answer a known question about that PDF. This is more valuable than unit
  testing the splitter in isolation.

- `main.py` routes — Use FastAPI's `TestClient` (wraps `httpx`):
  - `POST /upload` with a valid PDF → expect 200 + a `session_id` string
  - `POST /upload` with a non-PDF → expect 400 or a useful error
  - `POST /chat` with a valid session → expect a streaming response
  - `POST /chat` with an invalid session_id → expect 404

**What not to test**: The exact content of LLM answers (non-deterministic), the internal
format of the session store dict, or ChromaDB internals.

---

## Out of Scope

- **Persistent sessions across server restarts** — would require a proper vector DB (Pinecone,
  Qdrant) or disk persistence, which adds cost and complexity
- **Multi-user auth** — no login, no per-user isolation
- **Conversation memory** — each question is stateless; the chat history shown in the UI
  is purely cosmetic and not passed back to the LLM. Adding memory via
  `RunnableWithMessageHistory` is a documented future enhancement
- **Scanned PDFs / OCR** — `PyPDFLoader` extracts text-layer only; image-based PDFs will
  return empty or poor results
- **File size limits** — no explicit cap; Render free tier has a 30-second request timeout
  which large PDFs may hit
- **Rate limiting** — Groq's free tier limits apply; no explicit handling in the app

---

## Further Notes

**Why this is a strong resume project:**

This project demonstrates a complete production-relevant RAG pipeline — the same
architecture used in enterprise document Q&A products — without hiding behind a single
`langchain.chains.RetrievalQA` call. The LCEL chain pattern, the per-session vector store
design, SSE streaming, and the local/cloud swap architecture are all things worth explaining
in depth in an interview. The deployment stack (Render + Vercel) shows you can ship, not
just prototype.

**Interview talking points to prepare:**
- Why in-memory ChromaDB over persistent? (Appropriate for the problem scope; trade-off is
  acknowledged.)
- Why Groq over OpenAI? (Free tier, no credit card; also faster inference — demonstrate you
  evaluate tools on fit, not just brand recognition.)
- Why HuggingFace embeddings? (CPU-friendly, free, no external API call per query — reduces
  latency and cost.)
- What would you change if this went to production? (Persistent vector store per user,
  Redis for session management, auth, rate limiting, chunking strategy experiments.)
- Why LCEL instead of the old chain classes? (LangChain 1.x deprecated them; LCEL is more
  composable, easier to stream, easier to debug with LangSmith.)

**LangChain package breakdown (important for imports):**
LangChain 1.x is split into multiple installable packages. Each provider has its own package.
Never import from the top-level `langchain` for provider-specific things:

| What you need | Import from |
|---|---|
| `ChatGroq` | `langchain_groq` |
| `ChatOllama` | `langchain_ollama` |
| `OllamaEmbeddings` | `langchain_ollama` |
| `HuggingFaceEmbeddings` | `langchain_huggingface` |
| `Chroma` | `langchain_chroma` |
| `PyPDFLoader` | `langchain_community.document_loaders` |
| `RecursiveCharacterTextSplitter` | `langchain_text_splitters` |
| `ChatPromptTemplate`, `RunnablePassthrough`, `StrOutputParser` | `langchain_core.*` |
