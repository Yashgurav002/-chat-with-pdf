import json
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from rag.chain import build_chain
from rag.pipeline import build_retriever, warmup_embeddings
from sessions import SESSION_STORE

load_dotenv()

app = FastAPI(title="Chat with PDF")

_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if frontend_url := os.getenv("FRONTEND_URL"):
    _cors_origins.append(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def preload_models():
    """Download embedding model at boot so the first /upload doesn't timeout."""
    if os.getenv("MODE", "production") == "production":
        warmup_embeddings()


class ChatRequest(BaseModel):
    session_id: str
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename and file.filename.lower().endswith(".pdf")):
            raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    session_id = str(uuid.uuid4())
    try:
        retriever, chunks = build_retriever(pdf_bytes, session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {exc}") from exc

    SESSION_STORE[session_id] = {"retriever": retriever, "chunks": chunks}
    page_count = max((c.metadata.get("page", 0) for c in chunks), default=-1) + 1

    return {
        "session_id": session_id,
        "page_count": page_count,
        "chunk_count": len(chunks),
    }


@app.post("/chat")
async def chat(body: ChatRequest):
    session = SESSION_STORE.get(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    retriever = session["retriever"]
    chain = build_chain(retriever)

    async def event_stream():
        try:
            async for token in chain.astream(body.question):
                yield f"data: {json.dumps({'token': token})}\n\n"

            source_docs = retriever.invoke(body.question)
            sources = [
                {
                    "page": doc.metadata.get("page", 0),
                    "text": doc.page_content,
                }
                for doc in source_docs
            ]
            yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Session not found")

    del SESSION_STORE[session_id]
    return {"deleted": True}
