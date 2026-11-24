import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Disable Chroma anonymous telemetry to suppress external network call warnings
os.environ["ANONYMIZED_TELEMETRY"] = "False"
# Ensure huggingface works fully offline once model is cached
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PERSIST_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "opsranger_runbooks"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_embeddings: Optional[HuggingFaceEmbeddings] = None
_vector_store: Optional[Chroma] = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """Initialize and return the local HuggingFace embeddings model."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def get_vector_store(persist_directory: Optional[Path] = None) -> Chroma:
    """Initialize and return the persistent Chroma vector store."""
    global _vector_store
    if _vector_store is None:
        persist_path = persist_directory or DEFAULT_PERSIST_DIR
        persist_path.mkdir(parents=True, exist_ok=True)
        embeddings = get_embeddings()
        _vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(persist_path),
            client_settings=Settings(
                anonymized_telemetry=False,
                is_persistent=True,
                persist_directory=str(persist_path),
            ),
        )
    return _vector_store


def add_documents_to_store(
    documents: List[Document],
    ids: Optional[List[str]] = None,
    vector_store: Optional[Chroma] = None,
) -> List[str]:
    """Add documents to the persistent Chroma store with deterministic IDs."""
    if not documents:
        return []
    store = vector_store or get_vector_store()
    return store.add_documents(documents=documents, ids=ids)


def query_runbooks(
    query: str,
    client_id: str,
    top_k: int = 4,
    vector_store: Optional[Chroma] = None,
) -> List[Dict[str, Any]]:
    """Retrieve runbook chunks strictly filtered by client_id.

    Args:
        query: Alert or symptom description to search for.
        client_id: Unique client identifier for tenant isolation.
        top_k: Number of relevant chunks to retrieve.
        vector_store: Optional vector store instance.

    Returns:
        List of result dictionaries containing content, metadata, and score.
    """
    store = vector_store or get_vector_store()

    # Strict multi-tenant isolation filter
    metadata_filter = {"client_id": client_id}

    # Retrieve matching documents with similarity score
    results_with_scores: List[Tuple[Document, float]] = (
        store.similarity_search_with_score(
            query=query,
            k=top_k,
            filter=metadata_filter,
        )
    )

    formatted_results = []
    for doc, distance in results_with_scores:
        # Cosine distance ranges from 0 (identical) to 2 (opposite)
        # Convert to an intuitive similarity score between 0.0 and 1.0
        similarity_score = max(0.0, 1.0 - (distance / 2.0))
        formatted_results.append(
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": round(similarity_score, 4),
                "distance": round(distance, 4),
            }
        )

    return formatted_results
