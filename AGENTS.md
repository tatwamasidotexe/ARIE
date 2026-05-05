# ARIE — Agent & Developer Guide

Concise reference for AI agents and humans extending the ARIE codebase.

---

## 1. Project overview

**ARIE** is an AI-powered retrieval and insight system. It ingests external structured data (primarily via RSS), stores it, and aims to support semantic retrieval with embeddings.

**Direction:** evolve from a retrieval stack (RAG) toward an **insight** system—clustering, trends, and recommendations—built on the same data and embeddings.

---

## 2. Architecture (high level)

| Layer | Technology / role |
|--------|-------------------|
| **Backend** | FastAPI (Python) |
| **Database** | PostgreSQL with **pgvector** |
| **Cache** | Redis (optional; not required for core behavior yet) |
| **Ingestion** | RSS-oriented Python scripts under `ingestion/` |
| **Frontend** | Next.js |
| **Agents / ML** | Planned: embeddings, clustering, graph-style logic (`agents/`, workflows) |

---

## 3. Data flow

```
External RSS sources → ingestion scripts → PostgreSQL → embeddings → retrieval → LLM → response
```

**Reality check:**

- **Ingestion** is partially implemented; behavior and persistence should be validated against the live schema.
- **Embeddings and retrieval** are in progress; the path from stored documents to vector search may be incomplete.
- The system is **not** fully end-to-end yet (no guaranteed RAG loop from query to grounded answer).

---

## 4. Current status (explicit)

- **Infrastructure:** Docker Compose (Postgres/pgvector, Redis, backend service definitions) is in place and usable for local development.
- **Backend API:** Exists; integration with embedding generation, storage, and retrieval may be partial or stubbed.
- **Ingestion:** RSS scripts exist; confirm rows (and any queue/stream handoff) match expectations before treating ingestion as “done.”
- **RAG:** No fully verified, production-style RAG loop yet.
- **Agentic behavior:** Not a goal for the current milestone; avoid bolting on autonomous agent frameworks prematurely.

---

## 5. Key directories

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI app (`app/main.py`, routes, DB access) |
| `frontend/` | Next.js UI |
| `ingestion/` | RSS fetchers and related ingest utilities |
| `agents/` | Embedding helpers and future agent / graph logic |
| `workflows/` | Background jobs / workers (e.g. stream consumers) |
| `database/` | Schema, migrations, and DB initialization scripts |

---

## 6. How to run (local)

1. **Infrastructure** (repository root):

   ```bash
   docker-compose up -d
   ```

2. **Backend** (from `backend/`):

   ```bash
   uvicorn app.main:app --reload
   ```

3. **Frontend** (from `frontend/`):

   ```bash
   npm install
   npm run dev
   ```

4. **Ingestion** (repository root; ensures `ingestion` package imports work):

   ```bash
   python -m ingestion.rss_fetcher
   ```

   If you run a script path directly, set `PYTHONPATH` to the repo root so imports resolve.

Configure environment variables (e.g. database and Redis URLs) via `.env` or your shell as required by `ingestion` and `backend`.

---

## 7. Development guidelines (for AI agents and contributors)

- **Do not** introduce unnecessary abstractions, frameworks, or “architecture for architecture’s sake.”
- **Prioritize** a working vertical slice: ingestion → storage → embeddings → retrieval → generation **before** new features.
- **Prefer** simple, explicit code over clever patterns.
- **Avoid** agent orchestration frameworks until the core pipeline is reliable and tested.
- **Validate each layer** before building the next (correct rows, correct vectors, correct top-k, then LLM).
- **Keep diffs small** and each change easy to reason about and test.

---

## 8. Immediate next steps

1. Ensure ingestion **writes correctly** to PostgreSQL (and any intermediate queues) per the intended schema.
2. Implement **embedding generation** and **storage** in pgvector (idempotent updates where appropriate).
3. Build and **validate retrieval** (top-k similarity search, sane defaults for chunking/metadata).
4. Complete a **minimal RAG loop**: query → retrieve → prompt → generate, with observable citations or source IDs.
5. Add **clustering** (e.g. K-Means or similar) for trend / theme detection on embeddings.

---

## 9. Notes

- **Redis** is available in Compose but **not** essential for the core story until workers and caching are defined.
- The project is in an **early integration** phase; favor clarity and correctness over complexity.
- When in doubt, **instrument and verify** (SQL counts, sample vectors, retrieval scores) instead of adding new moving parts.