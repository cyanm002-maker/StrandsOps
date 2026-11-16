1. What Are We Making?
We are building OpsRanger (Incident Copilot) — an autonomous AI agent designed for Managed Service Providers (MSPs).

When cloud infrastructure throws an alert (like a database crashing or CPU spiking), junior engineers often lack the specific context or client runbooks needed to fix it quickly. This agent automatically catches the alert, investigates the logs, looks up that specific client's past history and runbooks, figures out the root cause, and either fixes it or asks a senior engineer on Slack/Teams for permission to execute a fix.

2. What Are the Core Features?
Automated Alert Triage: Automatically catches CloudWatch alerts the second they happen without waiting for a human to notice.

Client-Isolated RAG (Knowledge Retrieval): Uses past tickets, architecture diagrams, and client-specific runbooks to fetch precise instructions, strictly separated by client_id so data never mixes between clients.

Autonomous Read-Only Diagnostics: Automatically runs safe, read-only diagnostic commands (fetching CloudWatch metrics and CloudTrail logs) to gather evidence.

Human-in-the-Loop Approval: Pauses before taking risky actions (like restarting a server) and sends an interactive approval prompt to Slack or Teams for a senior engineer to click "Approve".

Auto-Documentation: Automatically writes a full incident summary and updates the ticketing system once resolved.

Semantic Caching: Instantly returns solutions for recurring alerts to keep the demo blazing fast.

3. How Are We Going to Implement It? (The Tech Stack & Workflow)
Your project uses a modern, multi-language polyglot architecture:

Frontend (React.js):

A live dashboard for MSP engineers to view incoming alerts, track active agent diagnostics, and manage pending human-approval queues.

Backend API & Webhooks (Node.js & Express):

Handles user requests, coordinates incident states, triggers Slack/Teams webhook notifications, and orchestrates the overall agent workflow.

RAG & Vector Search Microservice (Python, FastAPI, LangChain & Chroma):

Ingests documents, splits them into text chunks, converts them into embeddings, and provides a vector search API with strict metadata filtering (client_id) so the agent only pulls the correct client context.

Agent & Cloud Integration (AWS Bedrock / OpenSearch / CloudWatch):

The agent reasons through the alert payload, queries the Python RAG microservice, and executes safe cloud diagnostic tools.