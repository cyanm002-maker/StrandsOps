import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.vectorstore import add_documents_to_store, get_vector_store

logger = logging.getLogger("rag_service.ingest")

# Initialize text splitter for operational runbooks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=120,
    separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
)


def generate_chunk_id(client_id: str, source_file: str, chunk_index: int, content: str) -> str:
    """Generate a stable, deterministic ID for Chroma deduplication."""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:10]
    safe_filename = Path(source_file).name.replace(" ", "_")
    return f"{client_id}::{safe_filename}::chunk_{chunk_index}::{content_hash}"


def ingest_text_content(
    content: str,
    client_id: str,
    source_file: str = "manual_entry.txt",
    doc_type: str = "runbook",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Split and ingest raw text content for a specific client into Chroma."""
    if not content.strip():
        return 0

    chunks = text_splitter.split_text(content)
    documents: List[Document] = []
    ids: List[str] = []

    for idx, chunk in enumerate(chunks):
        metadata = {
            "client_id": client_id,
            "doc_type": doc_type,
            "source_file": source_file,
            "chunk_index": idx,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        chunk_id = generate_chunk_id(client_id, source_file, idx, chunk)
        documents.append(Document(page_content=chunk, metadata=metadata))
        ids.append(chunk_id)

    store = get_vector_store()
    add_documents_to_store(documents=documents, ids=ids, vector_store=store)
    logger.info(
        "Ingested %d chunk(s) for client '%s' from '%s'",
        len(documents),
        client_id,
        source_file,
    )
    return len(documents)


def scan_and_ingest_data_directory(data_dir: Path) -> Dict[str, Any]:
    """Scan data/ for client subdirectories and ingest all .txt runbooks.

    Expected structure:
    data/
      ├── client_alpha/
      │   ├── database_failover.txt
      │   └── payment_gateway_timeout.txt
      └── client_beta/
          ├── kubernetes_oom_killed.txt
          └── redis_cache_eviction.txt

    Returns summary of ingested files and chunks per client.
    """
    summary: Dict[str, Any] = {
        "clients_scanned": 0,
        "files_processed": 0,
        "total_chunks_ingested": 0,
        "client_breakdown": {},
    }

    if not data_dir.exists() or not data_dir.is_dir():
        logger.warning("Data directory does not exist: %s", data_dir)
        return summary

    for client_entry in sorted(data_dir.iterdir()):
        if not client_entry.is_dir():
            continue
        # Skip hidden folders or python caches
        if client_entry.name.startswith((".", "_")):
            continue

        client_id = client_entry.name
        summary["clients_scanned"] += 1
        summary["client_breakdown"][client_id] = {
            "files": [],
            "chunks_ingested": 0,
        }

        txt_files = sorted(client_entry.glob("*.txt"))
        for txt_file in txt_files:
            try:
                content = txt_file.read_text(encoding="utf-8")
                chunks_count = ingest_text_content(
                    content=content,
                    client_id=client_id,
                    source_file=txt_file.name,
                    doc_type="runbook",
                )
                summary["files_processed"] += 1
                summary["total_chunks_ingested"] += chunks_count
                summary["client_breakdown"][client_id]["files"].append(txt_file.name)
                summary["client_breakdown"][client_id]["chunks_ingested"] += chunks_count
            except Exception as e:
                logger.error("Error reading %s: %s", txt_file, e)

    return summary
