import json
import os
import uuid

from dotenv import load_dotenv
from typing import Annotated, List
from langchain_core.messages import HumanMessage, AIMessage
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List

from rag.chain import build_chain
from rag.pipeline import build_retriever, warmup_embeddings
from sessions import SESSION_STORE

load_dotenv()

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB

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
    if os.getenv("MODE", "production") == "production":
        warmup_embeddings()


class ChatRequest(BaseModel):
    session_id: str
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


# ── original single-file endpoint (unchanged) ──────────────────────────────
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename and file.filename.lower().endswith(".pdf")):
            raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF must be 10 MB or smaller")

    session_id = str(uuid.uuid4())
    try:
        retriever, chunks = build_retriever(
            [(pdf_bytes, file.filename or "document.pdf")], session_id
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {exc}") from exc

    SESSION_STORE[session_id] = {"retriever": retriever, "chunks": chunks}
    page_count = max((c.metadata.get("page", 0) for c in chunks), default=-1) + 1

    return {
        "session_id": session_id,
        "page_count": page_count,
        "chunk_count": len(chunks),
    }


# ── new multi-file endpoint ─────────────────────────────────────────────────
@app.post("/upload-multiple")
async def upload_multiple(files: Annotated[List[UploadFile], File(...)]):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    file_payloads = []
    for file in files:
        if file.content_type not in ("application/pdf", "application/octet-stream"):
            if not (file.filename and file.filename.lower().endswith(".pdf")):
                raise HTTPException(
                    status_code=400,
                    detail=f"{file.filename} is not a PDF",
                )

        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail=f"{file.filename} is empty")
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} exceeds 10 MB limit",
            )
        file_payloads.append((pdf_bytes, file.filename or "document.pdf"))

    session_id = str(uuid.uuid4())
    try:
        retriever, chunks = build_retriever(file_payloads, session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process PDFs: {exc}") from exc

    SESSION_STORE[session_id] = {"retriever": retriever, "chunks": chunks}

    page_count = max((c.metadata.get("page", 0) for c in chunks), default=-1) + 1
    doc_names = [name for _, name in file_payloads]

    return {
        "session_id": session_id,
        "doc_count": len(file_payloads),
        "doc_names": doc_names,
        "page_count": page_count,
        "chunk_count": len(chunks),
    }


# ── chat (unchanged) ────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(body: ChatRequest):
    session = SESSION_STORE.get(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # initialise history list if first message in session
    if "chat_history" not in session:
        session["chat_history"] = []

    retriever = session["retriever"]
    chain = build_chain(retriever, chat_history=session["chat_history"])

    full_response = ""

    async def event_stream():
        nonlocal full_response
        try:
            async for token in chain.astream(body.question):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"

            source_docs = retriever.invoke(body.question)
            sources = [
                {
                    "page": doc.metadata.get("page", 0),
                    "source_file": doc.metadata.get("source_file", ""),
                    "text": doc.page_content,
                }
                for doc in source_docs
            ]

            # save turn to history after response is complete
            session["chat_history"].append(HumanMessage(content=body.question))
            session["chat_history"].append(AIMessage(content=full_response))

            yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )