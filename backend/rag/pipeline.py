import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    mode = os.getenv("MODE", "production")
    if mode == "local":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        _embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)
    else:
        _embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    return _embeddings


def warmup_embeddings():
    _get_embeddings()


def build_retriever(
    files: list[tuple[bytes, str]],  # list of (pdf_bytes, filename)
    session_id: str,
) -> tuple[VectorStoreRetriever, list]:
    """
    Build a single retriever over one or more PDFs.
    Each file is (pdf_bytes, filename). All chunks land in one Chroma collection.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    all_chunks = []

    for pdf_bytes, filename in files:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            documents = PyPDFLoader(tmp_path).load()
            # tag every chunk with its source filename
            for doc in documents:
                doc.metadata["source_file"] = filename

            chunks = filter_complex_metadata(splitter.split_documents(documents))
            all_chunks.extend(chunks)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    vectorstore = Chroma(
        collection_name=session_id,
        embedding_function=_get_embeddings(),
    )
    vectorstore.add_documents(all_chunks)

    return vectorstore.as_retriever(search_kwargs={"k": 4}), all_chunks