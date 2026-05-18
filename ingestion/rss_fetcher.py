"""RSS feed fetcher — staged ingestion: ingest → embed → insight pipeline."""
import json
import logging
import time
import uuid

import feedparser
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from agents.embeddings import store_document
from agents.graph import run_pipeline
from ingestion.config import DATABASE_URL

logger = logging.getLogger(__name__)

FEEDS = [
    "https://hnrss.org/frontpage",
    "https://stackoverflow.com/feeds",
]
FEED_ENTRY_LIMIT = 500


def get_db():
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    return engine, sessionmaker(bind=engine)()


def extract_entry_content(entry) -> str:
    """Prefer full content, then summary, then description."""
    content_list = entry.get("content")
    if content_list:
        first = content_list[0]
        value = first.get("value") if hasattr(first, "get") else getattr(first, "value", "")
        if value:
            return value
    return entry.get("summary", "") or entry.get("description", "") or ""


def fetch_hn_comments(item_id: str, max_comments: int = 5) -> str:
    """Fetch top-level HN comments and return as text."""
    logger.debug("Fetching HN comments for item: %s", item_id)
    try:
        url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
        data = requests.get(url, timeout=5).json()

        if not data or "kids" not in data:
            return ""

        comments = []
        start_time = time.time()
        for cid in data["kids"][:max_comments]:
            if time.time() - start_time > 2:
                break
            cdata = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{cid}.json",
                timeout=5,
            ).json()
            if cdata and cdata.get("text"):
                comments.append(cdata["text"])

        return "\n\n".join(comments)
    except Exception as exc:
        logger.warning("HN comment fetch error for item %s: %s", item_id, exc)
        return ""


def fetch_feed(url: str) -> list[dict]:
    """Parse RSS feed and return normalized entries."""
    try:
        parsed = feedparser.parse(url, agent="ARIE/1.0")
        entries = []
        for entry in parsed.entries[:FEED_ENTRY_LIMIT]:
            link = entry.get("link", "")
            comments_link = entry.get("comments", "")
            hn_comments = ""

            if comments_link and "news.ycombinator.com/item?id=" in comments_link:
                try:
                    item_id = comments_link.split("id=")[-1]
                    hn_comments = fetch_hn_comments(item_id)
                except Exception:
                    pass

            base_content = extract_entry_content(entry)
            full_content = (
                f"{base_content}\n\n{hn_comments}" if hn_comments else base_content
            )
            entries.append(
                {
                    "external_id": entry.get("id") or link or str(uuid.uuid4()),
                    "title": entry.get("title", ""),
                    "content": full_content,
                    "url": link,
                    "author": entry.get("author"),
                }
            )
        return entries
    except Exception as exc:
        logger.error("Error fetching feed %s: %s", url, exc)
        return []


def resolve_source(url: str) -> str:
    if "stackoverflow.com" in url:
        return "stackoverflow"
    if "hnrss" in url:
        return "hn"
    return "rss"


def store_raw_post(db, entry: dict, source: str) -> str | None:
    """Insert a raw post. Returns raw_post_id on new insert, None on duplicate."""
    external_id = f"{source}:{entry['external_id'][:200]}"
    try:
        row = db.execute(
            text(
                """
                INSERT INTO raw_posts (id, source, external_id, title, content, url, author, metadata)
                VALUES (:id, :source, :external_id, :title, :content, :url, :author, '{}'::jsonb)
                ON CONFLICT (external_id) DO NOTHING
                RETURNING id
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "source": source,
                "external_id": external_id,
                "title": entry["title"][:2000],
                "content": (entry.get("content") or "")[:50000],
                "url": entry.get("url"),
                "author": entry.get("author"),
            },
        ).fetchone()
        db.commit()
        if row:
            return str(row[0])
        logger.debug("Skipped duplicate raw post: %s", external_id)
        return None
    except Exception as exc:
        db.rollback()
        logger.error("Error storing raw post %s: %s", external_id, exc)
        return None


def ingest_all_feeds(db, feeds: list[str]) -> list[dict]:
    """Phase 1: fetch feeds and store all raw posts."""
    stored_posts: list[dict] = []
    logger.info("=== PHASE 1: INGEST + STORE RAW POSTS ===")

    for url in feeds:
        source = resolve_source(url)
        logger.info("Fetching feed: %s (source=%s)", url, source)
        entries = fetch_feed(url)
        logger.info("Parsed %d entries from %s", len(entries), url)

        for i, entry in enumerate(entries, start=1):
            raw_post_id = store_raw_post(db, entry, source)
            if raw_post_id:
                stored_posts.append(
                    {
                        "raw_post_id": raw_post_id,
                        "source": source,
                        "title": entry["title"],
                        "content": entry.get("content") or "",
                    }
                )
                logger.info(
                    "Stored raw post %d/%d: %s",
                    i,
                    len(entries),
                    entry["title"][:80],
                )

    logger.info(
        "Phase 1 complete: %d new raw posts stored across %d feeds",
        len(stored_posts),
        len(feeds),
    )
    return stored_posts


def generate_embeddings(stored_posts: list[dict]) -> dict[str, str]:
    """Phase 2: embed all stored posts after corpus ingestion."""
    doc_ids: dict[str, str] = {}
    total = len(stored_posts)
    logger.info("=== PHASE 2: GENERATE EMBEDDINGS (%d posts) ===", total)

    for i, post in enumerate(stored_posts, start=1):
        raw_post_id = post["raw_post_id"]
        title = post["title"]
        content = post["content"] or title
        try:
            doc_id = store_document(raw_post_id, post["source"], title, content)
            doc_ids[raw_post_id] = doc_id
            logger.info(
                "Embedded %d/%d: %s (doc_id=%s)",
                i,
                total,
                title[:80],
                doc_id,
            )
        except Exception as exc:
            logger.error(
                "Embedding failed %d/%d for raw_post_id=%s: %s",
                i,
                total,
                raw_post_id,
                exc,
            )

    logger.info(
        "Phase 2 complete: %d/%d embeddings generated",
        len(doc_ids),
        total,
    )
    return doc_ids


def store_pipeline_report(engine, doc_id: str, report: dict) -> None:
    """Persist problem and insight report from pipeline output."""
    problem_id = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO problems (id, summary, frequency_score, document_ids, status)
                VALUES (:id, :summary, 1.0, ARRAY[CAST(:doc_id AS uuid)], 'synthesized')
                """
            ),
            {
                "id": problem_id,
                "summary": report.get("problem_summary", "Unknown"),
                "doc_id": doc_id,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO insight_reports (
                    id, problem_id, problem_summary,
                    evidence, root_causes, solutions,
                    confidence_score, sources, governance_checks
                )
                VALUES (
                    :id, :problem_id, :problem_summary,
                    CAST(:evidence AS jsonb),
                    CAST(:root_causes AS jsonb),
                    CAST(:solutions AS jsonb),
                    :confidence_score,
                    CAST(:sources AS jsonb),
                    CAST(:governance AS jsonb)
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "problem_id": problem_id,
                "problem_summary": report.get("problem_summary", ""),
                "evidence": json.dumps(report.get("evidence", [])),
                "root_causes": json.dumps(report.get("root_causes", [])),
                "solutions": json.dumps(report.get("solutions", [])),
                "confidence_score": report.get("confidence_score", 0.5),
                "sources": json.dumps(report.get("sources", [])),
                "governance": json.dumps(report.get("governance_checks", {})),
            },
        )
        conn.commit()
    logger.info(
        "Stored report for problem: %s",
        report.get("problem_summary", "")[:80],
    )


def run_insight_pipeline(
    engine, stored_posts: list[dict], doc_ids: dict[str, str]
) -> None:
    """Phase 3: run insight pipeline after full corpus embedding."""
    total = len(stored_posts)
    logger.info("=== PHASE 3: RUN INSIGHT PIPELINE (%d posts) ===", total)

    succeeded = 0
    for i, post in enumerate(stored_posts, start=1):
        raw_post_id = post["raw_post_id"]
        title = post["title"]
        content = post["content"] or title
        doc_id = doc_ids.get(raw_post_id)

        if not doc_id:
            logger.warning(
                "Skipping pipeline %d/%d — no document for raw_post_id=%s",
                i,
                total,
                raw_post_id,
            )
            continue

        try:
            logger.info(
                "Running pipeline %d/%d: %s",
                i,
                total,
                title[:80],
            )
            report = run_pipeline(raw_post_id, title, content)
            if not report:
                logger.warning(
                    "Pipeline returned empty report for raw_post_id=%s",
                    raw_post_id,
                )
                continue
            store_pipeline_report(engine, doc_id, report)
            succeeded += 1
        except Exception as exc:
            logger.error(
                "Pipeline failed %d/%d for raw_post_id=%s: %s",
                i,
                total,
                raw_post_id,
                exc,
            )

    logger.info(
        "Phase 3 complete: %d/%d reports stored",
        succeeded,
        total,
    )


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    engine, db = get_db()
    try:
        stored_posts = ingest_all_feeds(db, FEEDS)
        if not stored_posts:
            logger.info("No new posts ingested; skipping embedding and pipeline phases")
            return

        doc_ids = generate_embeddings(stored_posts)
        run_insight_pipeline(engine, stored_posts, doc_ids)
    finally:
        db.close()


if __name__ == "__main__":
    main()