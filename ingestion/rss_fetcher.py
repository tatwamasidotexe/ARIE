"""RSS feed fetcher — Stage 1: ingest and store raw_posts only."""
import logging
import time
import uuid

import feedparser
import requests
from sqlalchemy import text
from bs4 import BeautifulSoup
import html
import re

from database.db import get_db

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Normalize RSS/HTML text into clean semantic text."""
    if not text:
        return ""

    text = html.unescape(text)

    text = BeautifulSoup(text, "html.parser").get_text(" ")

    text = re.sub(r"\s+", " ", text).strip()

    return text

FEEDS = [
    "https://hnrss.org/frontpage",
    "https://stackoverflow.com/feeds",
]
FEED_ENTRY_LIMIT = 500

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
                comments.append(clean_text(cdata["text"]))

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

            base_content = clean_text(extract_entry_content(entry))
            full_content = (
                f"{base_content}\n\n{hn_comments}" if hn_comments else base_content
            )
            entries.append(
                {
                    "external_id": entry.get("id") or link or str(uuid.uuid4()),
                    "title": clean_text(entry.get("title", "")),
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
        return None
    except Exception as exc:
        db.rollback()
        logger.error("Failed to store %s: %s", external_id, exc)
        raise


def ingest_feed(db, url: str) -> dict[str, int]:
    """Ingest one feed. Returns counts: fetched, inserted, skipped, failed."""
    source = resolve_source(url)
    logger.info("Fetching feed: %s (source=%s)", url, source)

    entries = fetch_feed(url)
    fetched = len(entries)
    inserted = 0
    skipped = 0
    failed = 0

    logger.info("Fetched %d entries from %s", fetched, url)

    for entry in entries:
        try:
            raw_post_id = store_raw_post(db, entry, source)
            if raw_post_id:
                inserted += 1
                logger.debug("Inserted: %s", entry["title"][:80])
            else:
                skipped += 1
        except Exception:
            failed += 1

    logger.info(
        "Feed %s — fetched=%d inserted=%d skipped=%d failed=%d",
        url,
        fetched,
        inserted,
        skipped,
        failed,
    )
    return {"fetched": fetched, "inserted": inserted, "skipped": skipped, "failed": failed}


def ingest_all_feeds(db, feeds: list[str]) -> dict[str, int]:
    """Ingest all configured feeds and return aggregate counts."""
    totals = {"fetched": 0, "inserted": 0, "skipped": 0, "failed": 0}

    logger.info("=== STAGE 1: INGEST RAW DATA ===")

    for url in feeds:
        counts = ingest_feed(db, url)
        for key in totals:
            totals[key] += counts[key]

    logger.info(
        "Ingestion complete — fetched=%d inserted=%d skipped=%d failed=%d",
        totals["fetched"],
        totals["inserted"],
        totals["skipped"],
        totals["failed"],
    )
    return totals


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    db = get_db()
    try:
        ingest_all_feeds(db, FEEDS)
    finally:
        db.close()


if __name__ == "__main__":
    main()
