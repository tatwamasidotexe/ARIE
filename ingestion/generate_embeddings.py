"""Stage 2: generate embeddings for raw_posts and populate documents table."""
import argparse
import logging

from sqlalchemy import text

from agents.embeddings import store_document
from database.db import get_db

logger = logging.getLogger(__name__)

UNEMBEDDED_QUERY = """
    SELECT r.id, r.source, r.title, r.content
    FROM raw_posts r
    WHERE NOT EXISTS (
        SELECT 1 FROM documents d WHERE d.raw_post_id = r.id
    )
    ORDER BY r.fetched_at
"""

ALL_RAW_POSTS_QUERY = """
    SELECT r.id, r.source, r.title, r.content
    FROM raw_posts r
    ORDER BY r.fetched_at
"""

def fetch_raw_posts(db, force: bool) -> list[dict]:
    query = ALL_RAW_POSTS_QUERY if force else UNEMBEDDED_QUERY
    rows = db.execute(text(query)).fetchall()
    return [
        {
            "raw_post_id": str(row[0]),
            "source": row[1],
            "title": row[2] or "",
            "content": row[3] or "",
        }
        for row in rows
    ]


def delete_existing_documents(db, raw_post_id: str) -> int:
    result = db.execute(
        text("DELETE FROM documents WHERE raw_post_id = :id"),
        {"id": raw_post_id},
    )
    db.commit()
    return result.rowcount


def embed_post(post: dict, force: bool, db) -> str | None:
    raw_post_id = post["raw_post_id"]
    title = post["title"]
    content = post["content"] or title

    if force:
        deleted = delete_existing_documents(db, raw_post_id)
        if deleted:
            logger.debug("Removed %d existing document(s) for raw_post_id=%s", deleted, raw_post_id)

    return store_document(raw_post_id, post["source"], title, content)


def count_already_embedded(db) -> int:
    return db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM raw_posts r
            WHERE EXISTS (SELECT 1 FROM documents d WHERE d.raw_post_id = r.id)
            """
        )
    ).scalar() or 0


def run_embedding_pass(db, force: bool) -> dict[str, int]:
    already_embedded = count_already_embedded(db) if not force else 0
    posts = fetch_raw_posts(db, force=force)
    total = len(posts)
    embedded = 0
    failed = 0

    mode = "force-regenerate" if force else "incremental"
    logger.info("=== STAGE 2: GENERATE EMBEDDINGS (%s, %d posts) ===", mode, total)
    if not force and already_embedded:
        logger.info("Skipping %d already-embedded raw posts", already_embedded)

    if total == 0:
        logger.info("No raw posts to embed")
        return {"total": 0, "embedded": 0, "failed": 0, "skipped": already_embedded}

    for i, post in enumerate(posts, start=1):
        raw_post_id = post["raw_post_id"]
        title = post["title"]
        try:
            doc_id = embed_post(post, force=force, db=db)
            embedded += 1
            logger.info(
                "Embedded %d/%d: %s (doc_id=%s)",
                i,
                total,
                title[:80],
                doc_id,
            )
        except Exception as exc:
            failed += 1
            logger.error(
                "Embedding failed %d/%d for raw_post_id=%s: %s",
                i,
                total,
                raw_post_id,
                exc,
            )

    logger.info(
        "Embedding complete — processed=%d embedded=%d failed=%d skipped=%d",
        total,
        embedded,
        failed,
        already_embedded,
    )
    return {"total": total, "embedded": embedded, "failed": failed, "skipped": already_embedded}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate document embeddings for raw_posts in the database.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate embeddings for all raw posts (replaces existing documents).",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    args = parse_args()
    _, db = get_db()
    try:
        run_embedding_pass(db, force=args.force)
    finally:
        db.close()


if __name__ == "__main__":
    main()