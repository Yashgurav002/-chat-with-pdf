"""Standalone script to verify the RAG ingestion pipeline."""

import sys
import uuid
from pathlib import Path

from rag.pipeline import build_retriever

DEFAULT_PDF = Path(__file__).parent / "test_data" / "sample.pdf"
QUESTION = "What is the capital of France?"


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)

    pdf_bytes = pdf_path.read_bytes()
    session_id = str(uuid.uuid4())

    print(f"Loading PDF: {pdf_path}")
    retriever, _chunks = build_retriever(pdf_bytes, session_id)

    print(f"\nQuery: {QUESTION}\n")
    chunks = retriever.invoke(QUESTION)

    print(f"Retrieved {len(chunks)} chunk(s):\n")
    for i, chunk in enumerate(chunks, start=1):
        page = chunk.metadata.get("page", "?")
        print(f"--- Chunk {i} (page {page}) ---")
        print(chunk.page_content.strip())
        print()


if __name__ == "__main__":
    main()
