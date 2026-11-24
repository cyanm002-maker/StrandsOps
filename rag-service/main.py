import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Ensure rag-service root is in sys.path for direct module resolution
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.ingest import ingest_text_content, scan_and_ingest_data_directory
from src.vectorstore import get_vector_store, query_runbooks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag_service.main")
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

DATA_DIR = CURRENT_DIR / "data"
PERSIST_DIR = CURRENT_DIR / "chroma_db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context: scans and ingests runbooks on startup."""
    logger.info("Initializing OpsRanger RAG service...")
    logger.info("Data directory: %s", DATA_DIR)
    logger.info("Chroma persistent DB directory: %s", PERSIST_DIR)

    # Initialize vector store
    store = get_vector_store(persist_directory=PERSIST_DIR)

    # Scan and index existing client runbooks from data/
    logger.info("Scanning data/ directory for client runbooks on startup...")
    ingest_summary = scan_and_ingest_data_directory(DATA_DIR)
    logger.info(
        "Startup indexing completed: %d client(s), %d file(s), %d total chunks ingested.",
        ingest_summary["clients_scanned"],
        ingest_summary["files_processed"],
        ingest_summary["total_chunks_ingested"],
    )

    yield

    logger.info("Shutting down OpsRanger RAG service.")


# Initialize FastAPI application
app = FastAPI(
    title="OpsRanger (Incident Copilot) RAG Service",
    description="Multi-tenant, client-isolated RAG microservice for incident triage and runbook retrieval.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Node.js Express backend and React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request & Response Schemas
class RetrieveRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Incident alert description, error log, or troubleshooting query",
        examples=["PostgreSQL database connection pool exhausted failover"],
    )
    client_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the client account (enforces strict data isolation)",
        examples=["client_alpha"],
    )
    top_k: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum number of relevant runbook chunks to retrieve",
    )


class RetrieveResultItem(BaseModel):
    content: str
    metadata: Dict[str, Any]
    score: float
    distance: float


class RetrieveResponse(BaseModel):
    query: str
    client_id: str
    results_count: int
    results: List[RetrieveResultItem]


class IngestRequest(BaseModel):
    client_id: str = Field(
        ...,
        min_length=1,
        description="Client identifier the runbook belongs to",
        examples=["client_alpha"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Raw runbook markdown or plaintext content",
        examples=["# New Incident Runbook\n\nSteps to restart worker services..."],
    )
    source_file: str = Field(
        default="manual_entry.txt",
        description="Source filename identifier",
        examples=["worker_restart.txt"],
    )
    doc_type: str = Field(
        default="runbook",
        description="Document category or type",
    )
    extra_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional metadata key-values",
    )


class IngestResponse(BaseModel):
    status: str
    client_id: str
    source_file: str
    chunks_ingested: int
    message: str


# Endpoints
@app.get("/", tags=["Info"])
def root() -> Dict[str, Any]:
    """Microservice root overview."""
    return {
        "service": "OpsRanger Incident Copilot - RAG Service",
        "status": "online",
        "docs_url": "/docs",
        "endpoints": {
            "health": "GET /health",
            "retrieve": "POST /retrieve",
            "ingest": "POST /ingest",
            "scan_data": "POST /ingest/scan",
        },
    }


@app.get("/health", tags=["Health"])
def health() -> Dict[str, str]:
    """Healthcheck endpoint for orchestrator / backend checks."""
    return {
        "status": "ok",
        "service": "OpsRanger RAG Microservice",
        "version": "1.0.0",
    }


@app.post("/retrieve", response_model=RetrieveResponse, tags=["RAG"])
def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """Retrieve relevant runbook instructions strictly isolated by client_id."""
    clean_client_id = request.client_id.strip()
    clean_query = request.query.strip()

    if not clean_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id cannot be empty or whitespace.",
        )
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query cannot be empty or whitespace.",
        )

    try:
        results = query_runbooks(
            query=clean_query,
            client_id=clean_client_id,
            top_k=request.top_k,
        )
        return RetrieveResponse(
            query=clean_query,
            client_id=clean_client_id,
            results_count=len(results),
            results=[RetrieveResultItem(**item) for item in results],
        )
    except Exception as e:
        logger.exception("Error during runbook retrieval: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {str(e)}",
        )


@app.post("/ingest", response_model=IngestResponse, tags=["RAG"])
def ingest_runbook(request: IngestRequest) -> IngestResponse:
    """Ingest new runbook text dynamically with client metadata without restarting the server."""
    clean_client_id = request.client_id.strip()
    clean_content = request.content.strip()

    if not clean_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id cannot be empty or whitespace.",
        )
    if not clean_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content cannot be empty or whitespace.",
        )

    try:
        chunks_count = ingest_text_content(
            content=clean_content,
            client_id=clean_client_id,
            source_file=request.source_file,
            doc_type=request.doc_type,
            extra_metadata=request.extra_metadata,
        )
        return IngestResponse(
            status="success",
            client_id=clean_client_id,
            source_file=request.source_file,
            chunks_ingested=chunks_count,
            message=f"Successfully ingested {chunks_count} chunk(s) for client '{clean_client_id}'.",
        )
    except Exception as e:
        logger.exception("Error ingesting runbook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@app.post("/ingest/scan", tags=["RAG"])
def rescan_data_directory() -> Dict[str, Any]:
    """Trigger an on-demand scan and ingestion of data/ for newly added .txt files."""
    try:
        summary = scan_and_ingest_data_directory(DATA_DIR)
        return {
            "status": "success",
            "message": "Data directory scanned and indexed successfully.",
            "summary": summary,
        }
    except Exception as e:
        logger.exception("Error scanning data directory: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data directory rescan failed: {str(e)}",
        )
