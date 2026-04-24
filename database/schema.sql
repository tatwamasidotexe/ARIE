-- ARIE Database Schema with pgvector
-- Run: psql $DATABASE_URL -f schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- Raw content from ingestion
CREATE TABLE raw_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL,  -- 'reddit', 'hackernews', 'rss'
    external_id VARCHAR(255) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    author VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_raw_posts_source ON raw_posts(source);
CREATE INDEX idx_raw_posts_created ON raw_posts(created_at DESC);
CREATE INDEX idx_raw_posts_external_id ON raw_posts(external_id);

-- Documents with embeddings for vector search
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_post_id UUID REFERENCES raw_posts(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- Groq all-MiniLM-L6-v2 dimension
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_documents_source ON documents(source);
CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Detected problems/clusters
CREATE TABLE problems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    summary TEXT NOT NULL,
    cluster_centroid vector(384),
    frequency_score FLOAT NOT NULL DEFAULT 0,
    document_ids UUID[] DEFAULT '{}',
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'detected'  -- detected, researching, synthesized
);

CREATE INDEX idx_problems_frequency ON problems(frequency_score DESC);
CREATE INDEX idx_problems_status ON problems(status);

-- Insight reports
CREATE TABLE insight_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    problem_id UUID REFERENCES problems(id) ON DELETE CASCADE,
    problem_summary TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    root_causes JSONB NOT NULL DEFAULT '[]',
    solutions JSONB NOT NULL DEFAULT '[]',
    confidence_score FLOAT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    sources JSONB NOT NULL DEFAULT '[]',
    governance_checks JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_problem ON insight_reports(problem_id);
CREATE INDEX idx_reports_confidence ON insight_reports(confidence_score DESC);
CREATE INDEX idx_reports_created ON insight_reports(created_at DESC);

-- Stream positions for Redis consumer groups
CREATE TABLE stream_checkpoints (
    stream_name VARCHAR(255) PRIMARY KEY,
    last_id VARCHAR(100) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
