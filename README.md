# ARIE - Autonomous Research & Insight Engine

Production-style AI platform that monitors internet discussions, detects emerging problems, researches context using AI agents, and generates structured insight reports.

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Next.js    │────▶│   FastAPI    │────▶│  PostgreSQL │
│  Dashboard  │     │   Backend    │     │  + pgvector │
└─────────────┘     └──────┬───────┘     └─────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │ Redis Streams│
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ Ingestion  │  │  LangGraph │  │  Workers   │
    │  Service   │  │   Agents   │  │            │
    └────────────┘  └────────────┘  └────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector
- Redis 7+

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Ingestion Service
```bash
cd ingestion
pip install -r requirements.txt
python -m ingestion.reddit_scraper
python -m ingestion.rss_fetcher
```

### Workers
```bash
cd workflows
pip install -r requirements.txt
python -m workflows.worker
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
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - For embeddings and LLM
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` - Reddit API

## Components

| Component | Description |
|-----------|-------------|
| **Ingestion** | Reddit API scraper, RSS feed fetcher |
| **Agents** | Problem detection, Research, Debate, Synthesis, Governance |
| **Workflows** | Redis Streams event-driven pipeline |
| **Backend** | FastAPI REST API |
| **Frontend** | Next.js dashboard for search and reports |

## Observability

- **Prometheus**: Metrics exposed at `GET /metrics`
- **OpenTelemetry**: Traces exported to OTLP endpoint (set `OTEL_EXPORTER_OTLP_ENDPOINT`)
