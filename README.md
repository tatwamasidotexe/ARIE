# ARIE - Autonomous Research & Insight Engine

Production-style AI platform that monitors internet discussions, detects emerging problems, researches context using AI agents, and generates structured insight reports.

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Next.js    │────▶│   FastAPI    │────▶│  PostgreSQL │
│  Dashboard  │     │   Backend    │     │  + pgvector │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌────────────┐
                    │  LangGraph │
                    │   Agents   │
                    └────────────┘
```

## Corpus pipeline (3 stages)

ARIE uses a **decoupled multi-stage pipeline**. Each stage runs independently so you can change embedding models, retrieval parameters, or prompts without re-ingesting data.

| Stage | Script | Purpose |
| ----- | ------ | ------- |
| **1 — Ingest** | `python -m ingestion.rss_fetcher` | Fetch RSS feeds, normalize content, store `raw_posts` only |
| **2 — Embed** | `python -m ingestion.generate_embeddings` | Generate embeddings, populate `documents` table |
| **3 — Insights** | `python -m workflows.run_insights` | Run LangGraph pipeline, store `problems` + `insight_reports` |

**Why decouple?** Retrieval quality depends on a fully populated vector corpus. Running embeddings and synthesis only after ingestion completes improves semantic neighborhoods and avoids self-retrieval bias during early corpus formation.

### Typical workflow

From the repository root (so package imports resolve):

```bash
# 1. Ingest corpus (safe to rerun — skips duplicates by external_id)
python -m ingestion.rss_fetcher

# 2. Generate embeddings (incremental — skips already-embedded posts)
python -m ingestion.generate_embeddings

# 3. Run insight synthesis (incremental — skips posts with existing reports)
python -m workflows.run_insights
```

### Experimentation flags

Regenerate embeddings after changing `HF_EMBEDDING_MODEL`:

```bash
python -m ingestion.generate_embeddings --force
```

Regenerate insights after changing prompts or confidence heuristics:

```bash
python -m workflows.run_insights --force
```

`--force` on embeddings deletes and recreates `documents` rows per raw post. `--force` on insights clears existing `problems` and `insight_reports` for each document before re-running the pipeline.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Ingestion & pipeline

```bash
pip install -r ingestion/requirements.txt
python -m ingestion.rss_fetcher
python -m ingestion.generate_embeddings
python -m workflows.run_insights
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - PostgreSQL connection string
- `GROQ_API_KEY` - For LLM (insight pipeline)
- `HF_EMBEDDING_MODEL` - Hugging Face embedding model (default: `BAAI/bge-small-en-v1.5`)

## Components

| Component     | Description                                                |
| ------------- | ---------------------------------------------------------- |
| **Ingestion** | RSS fetcher (`rss_fetcher`) + embedding generator (`generate_embeddings`) |
| **Agents**    | Problem detection, Research, Debate, Synthesis, Governance |
| **Workflows** | Insight runner (`run_insights`)                            |
| **Backend**   | FastAPI REST API                                           |
| **Frontend**  | Next.js dashboard for search and reports                   |

## Observability

- **Prometheus**: Metrics exposed at `GET /metrics`
- **OpenTelemetry**: Traces exported to OTLP endpoint (set `OTEL_EXPORTER_OTLP_ENDPOINT`)
