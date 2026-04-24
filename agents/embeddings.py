"""Document embedding and vector storage."""
import uuid
from typing import List

from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer

from agents.config import DATABASE_URL, HF_EMBEDDING_MODEL

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(HF_EMBEDDING_MODEL)
    return _embedder


def get_embedding(text: str) -> List[float]:
    """Generate embedding for text."""
    model = _get_embedder()
    # sentence-transformers can handle long strings; we keep a conservative cap
    vec = model.encode(text[:8000], normalize_embeddings=True)
    return vec.tolist()


def store_document(raw_post_id: str, source: str, title: str, content: str) -> str:
    """Store document with embedding in PostgreSQL."""
    if not content.strip():
        content = title
    text_to_embed = f"{title}\n\n{content}"[:8000]
    embedding = get_embedding(text_to_embed)
    engine = create_engine(DATABASE_URL)
    doc_id = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO documents (id, raw_post_id, source, title, content, embedding)
            VALUES (:id, :raw_post_id, :source, :title, :content, :embedding)
            """),
            {
                "id": doc_id,
                "raw_post_id": raw_post_id,
                "source": source,
                "title": title[:2000],
                "content": content[:50000],
                "embedding": embedding,
            },
        )
        conn.commit()
    return doc_id


def vector_search(query: str, top_k: int = 10) -> List[dict]:
    """Search documents by semantic similarity."""
    qvec = get_embedding(query[:8000])
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT id, title, content, source,
                   1 - (embedding <=> CAST(:qvec AS vector)) AS similarity
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """),
            {"qvec": qvec, "top_k": top_k},
        ).fetchall()
    return [
        {
            "id": str(r[0]),
            "title": r[1],
            "content": r[2],
            "source": r[3],
            "similarity": float(r[4]),
        }
        for r in rows
    ]
