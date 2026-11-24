# OpsRanger: Incident Copilot (Amazon MSP Hackathon)

An autonomous alert-to-resolution assistant for **Managed Service Providers (MSPs)**. When an infrastructure alert arrives, the system retrieves client-specific runbooks and incident context with strict tenant isolation (`client_id`), runs safe read-only diagnostics, routes risky remediations for human approval, and drafts an incident summary.

## Architecture Overview

- **Frontend (`client/`):** React.js dashboard for viewing alerts, diagnostic steps, and human-in-the-loop approvals.
- **Backend API (`server/`):** Node.js + Express (JavaScript) server receiving alert payloads, calling the Python RAG service, coordinating agent/diagnostic logic, and handling approval workflows.
- **RAG Microservice (`rag-service/`):** Python + FastAPI microservice using `langchain-text-splitters`, `langchain-huggingface` (`all-MiniLM-L6-v2`), and `Chroma` to index `.txt` runbooks with `client_id` metadata filtering—running locally with zero paid LLM API keys required for retrieval.

## Project Structure

```text
incident-copilot/
├── README.md
├── backend.md                   # Beginner step-by-step guide for the Node.js backend
├── .env.example
├── .gitignore
├── client/                      # React.js frontend
├── server/                      # Node.js / Express backend (JavaScript)
│   ├── package.json
│   └── src/
│       └── index.js
└── rag-service/                 # Python FastAPI RAG microservice
    ├── requirements.txt
    ├── main.py
    └── data/
        ├── client_alpha/
        │   └── runbook_db.txt
        └── client_beta/
            └── runbook_cpu.txt
```

## Team Responsibilities

1. **RAG Microservice (`rag-service/`):**
   - Organize `.txt` runbooks by client folder (`data/<client_id>/*.txt`).
   - Chunk text with `RecursiveCharacterTextSplitter` and attach `client_id`, `doc_type`, and `source_file` metadata.
   - Generate embeddings locally with `all-MiniLM-L6-v2`, store them in ChromaDB (`./chroma_db`), and expose `POST /retrieve` with strict `client_id` filtering.
2. **Backend API (`server/`):**
   - Build Express routes (starting with `GET /health` and `POST /api/v1/alerts`).
   - Call `http://localhost:8000/retrieve` via `axios` using `alert_message` and `client_id`.
   - Add diagnostic checks, human-in-the-loop approval endpoints, and incident summary generation. See `backend.md` for a beginner walkthrough.
3. **Frontend (`client/`):**
   - Display incoming alerts, retrieved runbook context, diagnostic logs, and approval controls.

## Quick Start (Local Development)

### 1. Start the Python RAG Microservice (`rag-service/`)

```bash
cd rag-service
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

Runs at `http://localhost:8000`.

### 2. Start the Node.js Backend (`server/`)

```bash
cd server
npm install
npm start
```

Runs at `http://localhost:5000` (configured to call `http://localhost:8000/retrieve`).

### 3. Start the React Frontend (`client/`)

```bash
cd client
npm install
npm run dev
```

## Testing with Postman

### Test RAG Retrieval Directly (`POST http://localhost:8000/retrieve`)

```json
{
  "query": "How do I fix database connection exhaustion?",
  "client_id": "client_alpha"
}
```

### Test Node.js Alert Endpoint (`POST http://localhost:5000/api/v1/alerts`)

```json
{
  "alert_message": "How do I fix database connection exhaustion?",
  "client_id": "client_alpha",
  "severity": "CRITICAL"
}
```

### Verify Client Isolation

Send the same query with `"client_id": "client_beta"`. Only `client_beta` runbooks should match—never `client_alpha` database runbooks.

## AWS Deployment Notes

- Containerize `rag-service/` and `server/` with Docker, push images to **Amazon ECR**, and deploy on **Amazon ECS** (or run on an **Amazon EC2** instance during early testing).
- Persist ChromaDB (`./chroma_db`) or sync client `.txt` runbooks from **Amazon S3** so restarts do not wipe indexed data.
- Host the built React `client/` bundle on **Amazon S3** (optionally behind **Amazon CloudFront**) and set `PYTHON_RAG_URL` and CORS origins accordingly.
