# GlobalTalent AI Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/LLM-GPT--4o--mini-green)](https://openai.com)
[![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-yellow)](https://www.trychroma.com/)
[![UiPath Maestro](https://img.shields.io/badge/UiPath-Maestro%20Case-orange)](https://www.uipath.com/)
[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-9cf)](https://docs.anthropic.com/en/docs/claude-code)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**UiPath AgentHack 2026 — Track 1: UiPath Maestro Case**

Multi-agent AI system for global talent relocation. Orchestrates document verification, visa compliance checks, and personalized relocation guidance for HR teams — orchestrated through **UiPath Maestro Case Management** on UiPath Automation Cloud.

> **Bonus Declaration:** This solution was built using **Claude Code** via **UiPath for Coding Agents**. AI agents (DocSentry, ComplianceAgent, RelocationAgent) are Python-based external agents coordinated by the UiPath Maestro Case orchestration layer.

## Architecture

The system uses UiPath Maestro Case Management as the orchestration layer, with Python AI agents as external task executors:

```
                         UiPath Automation Cloud
                     +---------------------------+
                     |   Maestro Case Management  |
                     |  (Stage orchestration)     |
                     +----------+----------------+
                                |
            +-------------------+-------------------+
            |                   |                   |
            v                   v                   v
+-------------------+  +-------------------+  +-------------------+
|   DocSentry       |  |  ComplianceAgent   |  |  RelocationAgent  |
|  OCR + LLM        |  |  RAG + Web + LLM   |  |  RAG + Web + LLM |
|  Passports/visas  |  |  Visa compliance   |  |  Relocation guide |
+-------------------+  +-------------------+  +-------------------+
            |                   |                   |
            v                   v                   v
     Extracted fields     PASS/FAIL + score     Relocation guide
    
              +---------------------+
              |  Slack Interactivity |
              |  Approve/Reject via  |
              |  interactive buttons |
              +---------------------+
```

### Case Stages (Maestro)

| Stage | Type | Actor | Exception? |
|-------|------|-------|------------|
| **Intake** | Automatic | System | - |
| **Document Verification** | Automatic | DocSentry Agent | Expired → Renewal, Low confidence → Manual Review |
| **Manual Review** | Human | HR Specialist | - |
| **Document Renewal** | Human | HR Specialist | - |
| **Compliance Check** | Automatic | ComplianceAgent | Fail → Compliance Remediation |
| **Compliance Remediation** | Human | HR Manager | - |
| **HR Review** | Human | HR Manager | - |
| **Relocation Planning** | Automatic | RelocationAgent | - |
| **Completed** | Terminal | - | - |
| **Rejected / Escalated** | Terminal | - | - |

### Agents

| Agent | Role | Technology |
|-------|------|------------|
| **DocSentry** | Extracts structured fields from passport/visa documents | Tesseract OCR, PyPDF, GPT-4o-mini |
| **ComplianceAgent** | Checks documents against destination visa rules | RAG (ChromaDB), Brave Web Search, GPT-4o-mini |
| **RelocationAgent** | Generates personalized relocation guides | RAG (ChromaDB), Brave Web Search, GPT-4o-mini |
| **CaseOrchestrator** | Coordinates pipeline with exception handling | Async Python, polling, webhooks |

## Features

- **UiPath Maestro Case orchestration** — full stage-based case management on UiPath Automation Cloud
- **Multi-agent pipeline** — document extraction → compliance → human review → relocation
- **Multi-document support** — upload multiple files per case (passport, visa, bank statements, etc.)
- **Exception-heavy workflows** — document expiry renewal, low-confidence manual review, compliance remediation, escalation
- **Human-in-the-loop** at 3 decision points: Manual Review, Compliance Remediation, HR Review
- **Slack interactive approvals** — approve/reject via Slack buttons with real-time updates
- **Live case timeline** — full stage transition history for dashboard display
- **Maestro webhook integration** — bidirectional communication between Maestro and Python agents
- **Retrieval-Augmented Generation (RAG)** via ChromaDB vector store
- **Live web search** via Brave API
- **Graceful degradation** when APIs or databases are unavailable
- **Result caching** to avoid redundant LLM calls
- **Retry logic** with exponential backoff

## Directory Structure

```
├── globaltalent/               AI agents (Python)
│   ├── agents/
│   │   ├── agent_cache.py      Singleton cache
│   │   ├── case_orchestrator.py Pipeline coordinator
│   │   ├── compliance_agent.py Visa compliance checking
│   │   ├── doc_sentry.py       Document OCR and field extraction
│   │   └── relocation_agent.py Relocation guide generation
│   ├── chroma_db/              Vector store (auto-generated)
│   ├── rag_docs/               Scraped visa and relocation guides
│   ├── test_docs/              Sample documents
│   ├── tests/                  Unit tests
│   ├── config.py               Configuration
│   ├── models.py               Pydantic data models
│   ├── prompts.py              Prompt templates
│   ├── logger.py               Logging setup
│   ├── main.py                 Entry point
│   ├── load_rag.py             Build vector store
│   └── scraper.py              Web scraper
├── slack/                      Slack notifier service
│   ├── slack_notifier.py       Standalone Slack notification server
│   └── test_slack.py           Slack notification tests
├── uipath_maestro/             UiPath Maestro case definition
│   ├── maestro_case_definition.json  Case stages & transitions
│   └── integration_guide.md         Deployment instructions
├── server.py                   FastAPI server (API + webhooks + Slack)
├── requirements.txt
├── .env                        API keys
└── README.md
```

## Prerequisites

- Python 3.10+
- Tesseract OCR (for DocSentry)
- API keys: OpenAI, Brave Search, Hugging Face (optional)
- UiPath Automation Cloud tenant with Maestro enabled
- Slack app with Bot Token and Interactivity

## Setup

### 1. Clone and create virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...
BRAVE_API_KEY=...
HF_TOKEN=hf_...

# UiPath Maestro configuration (GT_ prefix)
GT_SLACK_BOT_TOKEN=xoxb-...
GT_SLACK_SIGNING_SECRET=...
GT_SLACK_CHANNEL_ID=C...
GT_SLACK_CANDIDATE_CHANNEL_ID=C...
GT_SLACK_MANAGER_ID=U...
GT_MAESTRO_WEBHOOK_SECRET=your-secret
```

### 4-7. Same as before (Tesseract, scrape, build RAG, verify)

## API Endpoints

### Cases

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/cases` | Create case (multi-file upload) |
| `GET` | `/api/cases` | List all cases |
| `GET` | `/api/cases/{id}` | Get case with documents & stages |
| `GET` | `/api/cases/{id}/stream` | SSE real-time progress |
| `GET` | `/api/cases/{id}/timeline` | Full stage transition history |

### Maestro Webhooks (called by UiPath Maestro)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/webhooks/maestro/document-verify` | Trigger document verification |
| `POST` | `/api/webhooks/maestro/compliance-check` | Trigger compliance check |
| `POST` | `/api/webhooks/maestro/relocation-guide` | Trigger relocation guide |
| `POST` | `/api/webhooks/maestro/hr-decision` | Receive HR approve/reject |
| `GET` | `/api/webhooks/maestro/case-status/{id}` | Poll case status |

### Slack

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/slack/interactive` | Handle Slack button clicks |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check with DB, cache, Slack status |

## Usage

### Creating a case (single document)

```bash
curl -X POST http://localhost:8000/api/cases \
  -F "files=@test_passport.png" \
  -F "destination_country=Germany" \
  -F "destination_city=Berlin" \
  -F "full_name=John Doe" \
  -F "family_size=3" \
  -F "monthly_budget_usd=5000"
```

### Creating a case (multiple documents)

```bash
curl -X POST http://localhost:8000/api/cases \
  -F "files=@passport.png" \
  -F "files=@visa.pdf" \
  -F "files=@bank_statement.pdf" \
  -F "destination_country=Canada" \
  -F "destination_city=Toronto" \
  -F "full_name=Jane Smith" \
  -F "family_size=2" \
  -F "monthly_budget_usd=7000"
```

### Watching case progress (SSE)

```bash
curl -N http://localhost:8000/api/cases/{case_id}?stream=true
```

### Getting case timeline

```bash
curl http://localhost:8000/api/cases/{case_id}/timeline
```

## UiPath Maestro Integration

See `uipath_maestro/integration_guide.md` for full deployment instructions.

Key steps:
1. Deploy this Python server publicly
2. Import `maestro_case_definition.json` into UiPath Maestro
3. Map webhook URLs to your server
4. Configure Slack interactivity
5. Cases created via API appear in Maestro Case Board

## Exception Flow Diagram

```
Document Verification
    ├── All docs OK ──────────────> Compliance Check
    ├── Expired doc detected ─────> Document Renewal → Re-verify
    └── Low confidence / failed ──> Manual Review
                                        ├── HR Approves ──> Compliance Check
                                        ├── HR Rejects ───> Rejected
                                        └── Escalates ────> Escalated

Compliance Check
    ├── PASS ─────────────────────> HR Review
    └── FAIL ────────────────────> Compliance Remediation
                                        ├── New docs ──> Re-check
                                        ├── HR Override ──> HR Review
                                        ├── Escalate ──> Escalated
                                        └── Reject ────> Rejected
```

## Supported Destinations

| Country | Visa Rules | City Guides |
|---------|-----------|-------------|
| Germany | germany_visa.txt | Berlin |
| United Kingdom | uk_visa.txt | London |
| Canada | canada_visa.txt | Toronto |
| United States | usa_visa.txt | - |
| UAE | uae_visa.txt | Dubai |

## Tech Stack

- **Orchestration:** UiPath Maestro Case Management (Automation Cloud)
- **Language:** Python 3.10+
- **LLM:** OpenAI GPT-4o-mini with streaming
- **Vector Database:** ChromaDB with OpenAI embeddings
- **OCR:** Tesseract + PyPDF2
- **Web Search:** Brave Search API
- **Notifications:** Slack interactive blocks
- **Backend:** FastAPI with async SQLite, SSE, LRU cache
- **Resilience:** Tenacity retry with exponential backoff
- **Built with:** Claude Code via UiPath for Coding Agents

## License

MIT
