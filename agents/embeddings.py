"""Document embedding and vector storage."""
import uuid
from typing import List

from sqlalchemy import text
from sentence_transformers import CrossEncoder, SentenceTransformer

from agents.config import HF_EMBEDDING_MODEL, HF_RERANKER_MODEL
from database.db import get_engine

_embedder: SentenceTransformer | None = None
_reranker: CrossEncoder | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(HF_EMBEDDING_MODEL)
    return _embedder


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(HF_RERANKER_MODEL)
    return _reranker


def get_embedding(text: str) -> List[float]:
    """Generate embedding for text."""
    model = _get_embedder()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def store_document(raw_post_id: str, source: str, title: str, content: str) -> str:
    """Store document with embedding in PostgreSQL."""
    if not content.strip():
        content = title
    text_to_embed = f"{title}\n\n{content}"
    embedding = get_embedding(text_to_embed)
    doc_id = str(uuid.uuid4())
    with get_engine().connect() as conn:
        conn.execute(
            text("""
            INSERT INTO documents (id, raw_post_id, source, title, content, embedding)
            VALUES (:id, :raw_post_id, :source, :title, :content, :embedding)
            """),
            {
                "id": doc_id,
                "raw_post_id": raw_post_id,
                "source": source,
                "title": title,
                "content": content,
                "embedding": embedding,
            },
        )
        conn.commit()
    return doc_id


def _format_document_text(title: str | None, content: str | None) -> str:
    title = title or ""
    content = content or ""
    return f"{title}\n\n{content}".strip()


def _rerank_results(query: str, results: List[dict]) -> List[dict]:
    """Rerank vector candidates with a cross-encoder relevance model."""
    if not results:
        return results

    reranker = _get_reranker()
    pairs = [
        [query, _format_document_text(result["title"], result["content"])]
        for result in results
    ]
    scores = reranker.predict(pairs)
    reranked = []
    for result, score in zip(results, scores):
        reranked.append({**result, "rerank_score": float(score)})
    return sorted(reranked, key=lambda item: item["rerank_score"], reverse=True)


def vector_search(
    query: str,
    top_k: int = 10,
    rerank: bool = True,
    candidate_k: int | None = None, #number of candidates to be reranked after vector search, override
) -> List[dict]:
    """Search documents by semantic similarity, optionally reranking candidates."""
    qvec = get_embedding(query)
     # vector search to return at least 20 rows for reranking
    limit = candidate_k if candidate_k is not None else max(top_k * 4, 20)
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("""
            SELECT id, title, content, source,
                   1 - (embedding <=> CAST(:qvec AS vector)) AS similarity
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """),
            {"qvec": qvec, "top_k": limit},
        ).fetchall()
    results = [
        {
            "id": str(r[0]),
            "title": r[1],
            "content": r[2],
            "source": r[3],
            "similarity": float(r[4]),
        }
        for r in rows
    ]
    if rerank:
        results = _rerank_results(query, results)
    return results[:top_k] #return the closest top_k vectors
