# 🛡️ OpsRanger: Incident Copilot (Amazon MSP Hackathon)

[![AWS](https://img.shields.io/badge/AWS-CloudWatch%20%7C%20Bedrock%20%7C%20ECS%20%7C%20S3-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![Node.js](https://img.shields.io/badge/Backend-Node.js%20%2B%20Express-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/RAG%20Service-Python%20%2B%20FastAPI-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Tailwind-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![VectorDB](https://img.shields.io/badge/Vector%20Store-ChromaDB%20%7C%20OpenSearch-purple?style=for-the-badge)](https://www.trychroma.com/)

**OpsRanger: Incident Copilot** is an autonomous, multi-tenant **Alert-to-Resolution AI Agent** engineered for **Managed Service Providers (MSPs)**. 

When cloud infrastructure alerts fire across hundreds of client accounts, junior on-call engineers often lack context regarding each client's unique architecture, past incidents, and custom runbooks. OpsRanger ingests incoming alerts, enforces strict tenant isolation (`client_id`) via Retrieval-Augmented Generation (RAG), executes safe read-only diagnostics, pauses high-risk remediations for **Human-in-the-Loop (HITL)** approval via Slack/Teams or the dashboard, and generates comprehensive post-incident summaries.

---

## 🏗️ Production System Architecture

OpsRanger utilizes a **polyglot microservice architecture** designed for low-latency alert triage, strict multi-tenant data isolation, and strategic caching.

> *Note: The diagrams below are rendered natively using GitHub-compatible Mermaid syntax.*

```mermaid
flowchart TB
    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E,font-weight:bold;
    classDef service fill:#1E293B,stroke:#38BDF8,stroke-width:2px,color:#F8FAFC;
    classDef cache fill:#DC2626,stroke:#FCA5A5,stroke-width:2px,color:#FEF2F2,font-weight:bold;
    classDef db fill:#4F46E5,stroke:#A5B4FC,stroke-width:2px,color:#EEF2FF;
    classDef human fill:#059669,stroke:#6EE7B7,stroke-width:2px,color:#ECFDF5,font-weight:bold;

    subgraph AWS_Trigger ["1. Alert Ingestion & Cloud Telemetry"]
        CW["Amazon CloudWatch<br/>(Alarms, Metrics, Logs)"]:::aws
        EB["Amazon EventBridge<br/>(Event Routing & Filtering)"]:::aws
        CT["AWS CloudTrail<br/>(Audit & Change Events)"]:::aws
    end

    subgraph Orchestration_Layer ["2. Core Orchestration & Agent Layer (ECS / Fargate)"]
        API["Node.js / Express API Gateway<br/>(server/)"]:::service
        REDIS[("Redis Semantic & State Cache<br/>(Deduplication & Incident State)")]:::cache
        AGENT["Strands Agent / Reasoning Engine<br/>(Root-Cause Hypothesis & Tool Calling)"]:::service
    end

    subgraph RAG_Layer ["3. Tenant-Isolated RAG Microservice (Python FastAPI)"]
        RAG_API["FastAPI RAG Service<br/>(rag-service/)"]:::service
        EMBED["Embedding Engine<br/>(all-MiniLM-L6-v2 / Titan)"]:::service
        VDB[("ChromaDB / OpenSearch Serverless<br/>Filtered by metadata: client_id")]:::db
        S3["Amazon S3 Runbook Vault<br/>(s3://msp-kb/client_id/*.txt)"]:::aws
    end

    subgraph HITL_UI ["4. Human-in-the-Loop (HITL) & Command Center"]
        SLACK["Slack / MS Teams Webhooks<br/>(Interactive Approval Cards)"]:::human
        REACT["React.js OpsRanger Dashboard<br/>(client/ via S3 + CloudFront)"]:::service
        ENG(("MSP On-Call Engineer")):::human
    end

    %% Connections
    CW -->|Alert Payload| EB
    EB -->|POST /api/v1/alerts| API
    API <-->|Check Alert Deduplication / Cache Hit| REDIS
    API --> AGENT

    AGENT <-->|Read-Only Diagnostics| CW
    AGENT <-->|Recent Config Changes| CT

    AGENT -->|POST /retrieve + client_id| RAG_API
    RAG_API --> EMBED
    EMBED <-->|Strict Tenant Metadata Filter| VDB
    S3 -.->|Document Sync & Chunking| RAG_API

    AGENT -->|Low-Risk: Auto-Summary| REACT
    AGENT -->|High-Risk Remediation: PENDING_APPROVAL| SLACK
    AGENT -->|Update Queue| REACT
    SLACK <-->|Approve / Reject| ENG
    REACT <-->|Inspect & Approve| ENG
    ENG -->|POST /api/v1/approvals/:id/resolve| API
```

---

## 🔄 Alert-to-Resolution Execution Flow (Sequence Diagram)

The following sequence illustrates how an incoming alert is deduplicated, enriched with tenant-isolated runbooks, diagnosed, and safely gated behind human approval:

```mermaid
sequenceDiagram
    autonumber
    actor Engineer as MSP Engineer
    participant CW as CloudWatch / EventBridge
    participant Node as Node.js Backend (server/)
    participant Cache as Redis / Semantic Cache
    participant RAG as Python RAG Service (rag-service/)
    participant Chroma as ChromaDB (Vector Store)
    participant Slack as Slack / React UI

    CW->>Node: POST /api/v1/alerts {client_id: "client_alpha", alert: "DB Pool Exhausted"}
    Node->>Cache: Check fingerprint hash (client_id + alert_signature)
    
    alt Cache Hit (Recurring Alert within TTL)
        Cache-->>Node: Return cached diagnosis & runbook context (<15ms)
    else Cache Miss (New Incident)
        Node->>RAG: POST /retrieve {query, client_id: "client_alpha"}
        RAG->>Chroma: similarity_search(query, filter={"client_id": "client_alpha"})
        Chroma-->>RAG: Top-k matching chunks (runbook_db.txt, past_ticket_4092.txt)
        RAG-->>Node: Return tenant-isolated context + source citations
        Node->>Node: Run read-only diagnostics & form Root-Cause Hypothesis
        Node->>Cache: Store diagnosis & set Incident State = PENDING_APPROVAL
    end

    Node->>Slack: Dispatch Approval Request (e.g., "Restart Payment ECS Task?")
    Slack->>Engineer: Notify On-Call Engineer with Hypothesis & Citations
    Engineer->>Slack: Clicks [Approve Remediation]
    Slack->>Node: POST /api/v1/approvals/:id/resolve {decision: "APPROVED"}
    Node-->>Slack: Generate & Post Final Incident Resolution Summary
```

---

## ⚡ Production Caching & Multi-Tenant Security Strategy

### 1. Multi-Layer Caching Architecture
To guarantee sub-second response times during alert storms and reduce redundant compute/LLM costs:
* **Alert Deduplication Cache:** Hashes incoming `(client_id + alert_name + resource_id)` with a configurable TTL (e.g., 5 minutes) to prevent duplicate incident threads when flapping CloudWatch alarms fire repeatedly.
* **Semantic Query Cache:** Caches frequent alert embeddings and their top-$k$ retrieved runbook chunks per `client_id` so recurring infrastructure issues bypass vector search overhead.
* **Persistent Embedding Model Cache:** Pre-loads `all-MiniLM-L6-v2` into memory at FastAPI startup so inference takes milliseconds without cold-start downloads.

### 2. Strict Multi-Tenant Isolation (`client_id`)
In an MSP environment, leaking **Client Alpha's** architecture or credentials into **Client Beta's** incident response is a critical security failure:
* Every ingested document chunk is stamped with mandatory metadata: `{"client_id": "<tenant>", "doc_type": "runbook|post_mortem|ticket", "source_file": "..."}`.
* All vector similarity queries enforce a hard pre-filter (`filter={"client_id": request.client_id}`) at the database level prior to distance scoring.

---

## 🗂️ Repository File Structure

```text
incident-copilot/
├── .env.example                     # Environment variable template
├── .gitignore
├── README.md                        # System architecture & documentation
│
├── client/                          # === FRONTEND (React.js / Vite / Tailwind) ===
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/              # Reusable UI (Navbar, AlertCard, ApprovalActionBox)
│       ├── pages/                   # Dashboard, IncidentDetail, ApprovalsQueue, Runbooks
│       └── services/                # Axios API clients
│
├── server/                          # === BACKEND ORCHESTRATOR (Node.js / Express) ===
│   ├── package.json
│   └── src/
│       ├── index.js                 # Express server entry point
│       ├── controllers/             # alert.controller.js, approval.controller.js
│       ├── routes/                  # /api/v1/alerts, /api/v1/approvals, /api/v1/incidents
│       ├── services/
│       │   ├── agent.service.js     # Coordinates RAG calls, diagnostics & hypothesis
│       │   ├── aws-tools.service.js # Read-only CloudWatch/CloudTrail diagnostic checks
│       │   └── notification.service.js # Slack / Teams webhook dispatcher
│       └── middlewares/             # Payload validation & centralized error handling
│
└── rag-service/                     # === RAG MICROSERVICE (Python / FastAPI) ===
    ├── requirements.txt             # FastAPI, LangChain, ChromaDB, HuggingFace
    ├── main.py                      # FastAPI server exposing /retrieve & /ingest
    ├── chroma_db/                   # Persistent local vector database storage
    ├── data/                        # Tenant-segregated knowledge base (.txt runbooks)
    │   ├── client_alpha/
    │   │   ├── runbook_db.txt
    │   │   └── past_ticket_4092.txt
    │   └── client_beta/
    │       └── runbook_cpu.txt
    └── src/
        ├── __init__.py
        ├── ingest.py                # RecursiveCharacterTextSplitter & metadata tagging
        ├── vectorstore.py           # ChromaDB & HuggingFace embedding initialization
        └── connectors.py            # Amazon S3 bucket runbook synchronization (boto3)
```

---

## 🛠️ Tech Stack & AWS Service Mapping

| Layer | Local / Hackathon MVP Stack | Production AWS Cloud Equivalent |
| :--- | :--- | :--- |
| **Alert Source & Routing** | Postman / Simulated JSON Webhooks | **Amazon CloudWatch** + **Amazon EventBridge** |
| **Backend Orchestrator** | Node.js + Express (`server/`) | **Amazon ECS (Fargate / Express Mode)** + **Amazon ECR** |
| **Agent & Reasoning** | Node.js Agent Service + Rule/LLM Loop | **Strands Agent on AgentCore** + **Amazon Bedrock** |
| **RAG Microservice** | Python + FastAPI (`rag-service/`) | **Amazon ECS** or **Amazon Bedrock Knowledge Bases** |
| **Embeddings** | `all-MiniLM-L6-v2` (Local, $0 API cost) | **Amazon Titan Text Embeddings** |
| **Vector Database** | ChromaDB (`./chroma_db` + EFS) | **Amazon OpenSearch Serverless** |
| **Document Storage** | Local `data/<client_id>/*.txt` | **Amazon S3** (Bucket prefixes per `client_id`) |
| **Frontend Dashboard** | React.js + Vite + Tailwind (`client/`) | **Amazon S3** + **Amazon CloudFront** (HTTPS CDN) |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
* **Node.js** `v18+` and `npm`
* **Python** `3.10+`
* **Postman** (for API & tenant-isolation verification)

### 1. Start the Python RAG Microservice (`rag-service/`)
Runs 100% locally with **zero paid API keys required**:

```bash
cd rag-service
python -m venv venv

# Activate virtual environment:
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
python main.py
```
> **Service active at:** `http://localhost:8000` (Interactive Swagger Docs: `http://localhost:8000/docs`)

### 2. Start the Node.js Backend Orchestrator (`server/`)

```bash
cd server
npm install
node src/index.js
```
> **Service active at:** `http://localhost:5000`

### 3. Start the React Frontend Dashboard (`client/`)

```bash
cd client
npm install
npm run dev
```
> **Dashboard active at:** `http://localhost:5173`

---

## 🧪 API Reference & Verification Tests

### 1. Trigger an Incoming Infrastructure Alert
**Endpoint:** `POST http://localhost:5000/api/v1/alerts`

```json
{
  "alert_message": "CRITICAL: Database connection pool exhausted on production RDS",
  "client_id": "client_alpha",
  "severity": "CRITICAL",
  "resource_id": "rds-prod-alpha-01"
}
```

**Sample Response:**
```json
{
  "incident_id": "INC-2026-8841",
  "client_id": "client_alpha",
  "status": "PENDING_APPROVAL",
  "root_cause_hypothesis": "Connection pool leak detected in payment microservice, matching historical Ticket #4092.",
  "retrieved_context": [
    {
      "content": "Step 1: Check active database connections via CloudWatch metrics. Step 2: Restart the offending ECS task gracefully...",
      "metadata": {
        "client_id": "client_alpha",
        "doc_type": "runbook",
        "source_file": "runbook_db.txt"
      }
    }
  ],
  "proposed_remediation": {
    "action": "RESTART_ECS_TASK",
    "risk_level": "HIGH",
    "requires_human_approval": true
  }
}
```

### 2. Verify Strict Tenant Isolation (`client_alpha` vs `client_beta`)
**Endpoint:** `POST http://localhost:8000/retrieve`

Send the exact same database query for `client_beta`:
```json
{
  "query": "How do I fix database connection exhaustion?",
  "client_id": "client_beta"
}
```
✅ **Expected Result:** Returns only `client_beta` documents (or an empty match array)—**never** leaking `client_alpha`'s database runbooks.

### 3. Approve or Reject High-Risk Remediation
**Endpoint:** `POST http://localhost:5000/api/v1/approvals/INC-2026-8841/resolve`

```json
{
  "decision": "APPROVED",
  "approved_by": "senior.engineer@msp-ops.io"
}
```

---

## ☁️ Production AWS Deployment Guide

1. **Containerize Services:** Build Docker images for `server/` (port `5000`) and `rag-service/` (port `8000`) and push both to **Amazon ECR**.
2. **Deploy Compute & Persistent Storage:**
   * Deploy both containers to **Amazon ECS (Fargate / Express Mode)**.
   * Mount an **Amazon EFS** volume to `/app/chroma_db` on the RAG task so vector embeddings persist across container restarts, and sync `.txt` runbooks from **Amazon S3**.
   * Set `PYTHON_RAG_URL` in the Node.js ECS task definition to the internal service discovery DNS of the Python RAG service.
3. **Host Frontend:** Run `npm run build` inside `client/`, upload `dist/` to an **Amazon S3** bucket, and serve globally over HTTPS via **Amazon CloudFront**.
4. **Connect Live Alerts:** Configure **Amazon CloudWatch Alarms** $\rightarrow$ **Amazon EventBridge** API Destinations to forward live alert payloads directly to `POST /api/v1/alerts`.
