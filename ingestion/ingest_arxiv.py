"""
arXiv ingestion — Stage 1: clean research metadata into raw_posts.

Fetches cs.AI / cs.LG / cs.CL / cs.IR via the official arXiv API, cleans text for
embedding-ready corpora, and upserts into PostgreSQL. No embeddings, queues, or PDFs.

Run from repository root:
    python -m ingestion.ingest_arxiv
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import text

from database.db import get_db
from ingestion.cleaners import clean_abstract, clean_arxiv_text, clean_title
from ingestion.config import DATABASE_URL

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_USER_AGENT = "ARIE-arxiv-ingest/1.0 (contact: local-dev)"

# Target taxonomy for retrieval corpus focus.
ARXIV_CATEGORIES = ("cs.AI", "cs.LG", "cs.MA", "cs.IR")

ARXIV_MAX_RESULTS = int(os.getenv("ARXIV_MAX_RESULTS", "500"))
ARXIV_DAYS_BACK = int(os.getenv("ARXIV_DAYS_BACK", "7"))

# arXiv recommends >= 3s between requests; pagination respects this.
ARXIV_REQUEST_DELAY_SEC = float(os.getenv("ARXIV_REQUEST_DELAY_SEC", "3"))
ARXIV_PAGE_SIZE = min(100, max(1, ARXIV_MAX_RESULTS))

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


def _atom(tag: str) -> str:
    return f"{{{ATOM_NS}}}{tag}"


def _arxiv(tag: str) -> str:
    return f"{{{ARXIV_NS}}}{tag}"


OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"


def _opensearch(tag: str) -> str:
    return f"{{{OPENSEARCH_NS}}}{tag}"


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published_at: datetime
    arxiv_url: str

def normalize_arxiv_id(raw_id: str) -> str:
    """Base id without version suffix — one corpus row per paper, not per revision."""
    return re.sub(r"v\d+$", "", raw_id.strip())

def extract_arxiv_id(entry_id: str) -> str:
    match = re.search(r"arxiv\.org/abs/([^/\s]+)", entry_id or "")
    if not match:
        return ""
    return normalize_arxiv_id(match.group(1))

def parse_published(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def build_search_query(category: str, days_back: int) -> str:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    # arXiv submittedDate uses YYYYMMDDHHMM in GMT.
    start_s = start.strftime("%Y%m%d") + "0000"
    end_s = end.strftime("%Y%m%d") + "2359"
    return f"cat:{category} AND submittedDate:[{start_s} TO {end_s}]"

def parse_entry(entry_el: ET.Element) -> ArxivPaper | None:
    entry_id = (entry_el.findtext(_atom("id")) or "").strip()
    arxiv_id = extract_arxiv_id(entry_id)
    if not arxiv_id:
        return None

    raw_title = entry_el.findtext(_atom("title")) or ""
    raw_summary = entry_el.findtext(_atom("summary")) or ""
    title = clean_title(raw_title)
    abstract = clean_abstract(raw_summary)

    if not title or not abstract:
        return None

    published_at = parse_published(entry_el.findtext(_atom("published")) or "")
    if published_at is None:
        return None

    authors: list[str] = []
    for author_el in entry_el.findall(_atom("author")):
        name = (author_el.findtext(_atom("name")) or "").strip()
        if name:
            authors.append(clean_arxiv_text(name))

    categories: list[str] = []
    for cat_el in entry_el.findall(_atom("category")):
        term = cat_el.attrib.get("term")
        if term:
            categories.append(term)
    for cat_el in entry_el.findall(_arxiv("primary_category")):
        term = cat_el.attrib.get("term")
        if term and term not in categories:
            categories.insert(0, term)

    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        categories=categories,
        published_at=published_at,
        arxiv_url=arxiv_url,
    )

def fetch_arxiv_page(
    client: httpx.Client,
    category: str,
    start: int,
    max_results: int,
    days_back: int,
) -> list[ArxivPaper]:
    params = {
        "search_query": build_search_query(category, days_back),
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = client.get(ARXIV_API_URL, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    total_results_el = root.find(_opensearch("totalResults"))
    if total_results_el is not None:
        logger.debug("category=%s api_total_results=%s", category, total_results_el.text)

    papers: list[ArxivPaper] = []
    for entry_el in root.findall(_atom("entry")):
        paper = parse_entry(entry_el)
        if paper:
            papers.append(paper)
    return papers


def fetch_category_papers(
    client: httpx.Client,
    category: str,
    max_results: int,
    days_back: int,
) -> list[ArxivPaper]:
    """Paginate arXiv API until max_results or empty page."""
    collected: list[ArxivPaper] = []
    start = 0

    while len(collected) < max_results:
        page_size = min(ARXIV_PAGE_SIZE, max_results - len(collected))
        try:
            page = fetch_arxiv_page(client, category, start, page_size, days_back)
        except httpx.HTTPError as exc:
            logger.error("category=%s api_failure=%s start=%d", category, exc, start)
            break

        if not page:
            break

        collected.extend(page)
        start += len(page)

        if len(page) < page_size:
            break # corpus exhausted, so exit while loop

        if len(collected) < max_results:
            time.sleep(ARXIV_REQUEST_DELAY_SEC)

    return collected[:max_results]


def paper_to_row(paper: ArxivPaper) -> dict[str, Any]:
    external_id = f"arxiv:{paper.arxiv_id}"
    metadata = {
        "arxiv_id": paper.arxiv_id,
        "authors": paper.authors,
        "categories": paper.categories,
        "arxiv_url": paper.arxiv_url,
        "published_at": paper.published_at.isoformat(),
    }
    author_str = "; ".join(paper.authors) if paper.authors else None
    if author_str and len(author_str) > 255:
        author_str = author_str[:252] + "..."

    return {
        "external_id": external_id,
        "title": paper.title[:2000],
        "content": paper.abstract[:50000],
        "url": paper.arxiv_url,
        "author": author_str,
        "created_at": paper.published_at.isoformat(),
        "metadata": metadata,
    }


def store_paper(db, row: dict[str, Any]) -> bool:
    """
    Insert one paper. Returns True if inserted, False if duplicate.

    published_at is stored in metadata; created_at holds paper publication time
    (raw_posts has no published_at column).
    """
    result = db.execute(
        text(
            """
            INSERT INTO raw_posts (
                id, source, external_id, title, content, url, author,
                created_at, metadata
            )
            VALUES (
                :id, 'arxiv', :external_id, :title, :content, :url, :author,
                COALESCE((:created_at)::timestamptz, NOW()),
                :metadata::jsonb
            )
            ON CONFLICT (external_id) DO NOTHING
            RETURNING id
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "external_id": row["external_id"],
            "title": row["title"],
            "content": row["content"],
            "url": row["url"],
            "author": row["author"],
            "created_at": row["created_at"],
            "metadata": json.dumps(row["metadata"]),
        },
    ).fetchone()
    db.commit()
    return result is not None


def ingest_category(
    db,
    client: httpx.Client,
    category: str,
    max_results: int,
    days_back: int,
) -> dict[str, int]:
    started = time.perf_counter()
    logger.info(
        "event=arxiv_fetch_start category=%s max_results=%d days_back=%d",
        category,
        max_results,
        days_back,
    )

    # fetch all data for the category
    papers = fetch_category_papers(client, category, max_results, days_back)
    fetched = len(papers)
    inserted = 0
    skipped_duplicate = 0
    failed = 0

    # insert to db one by one
    for paper in papers:
        row = paper_to_row(paper)
        try:
            if store_paper(db, row):
                inserted += 1
            else:
                skipped_duplicate += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            logger.error(
                "event=arxiv_insert_failed arxiv_id=%s error=%s",
                paper.arxiv_id,
                exc,
            )

    duration = time.perf_counter() - started
    logger.info(
        "event=arxiv_category_done category=%s fetched=%d inserted=%d "
        "duplicates_skipped=%d failed=%d duration_sec=%.2f",
        category,
        fetched,
        inserted,
        skipped_duplicate,
        failed,
        duration,
    )
    return {
        "fetched": fetched,
        "inserted": inserted,
        "duplicates_skipped": skipped_duplicate,
        "failed": failed,
    }


def ingest_arxiv(
    db,
    categories: tuple[str, ...] = ARXIV_CATEGORIES,
    max_results: int = ARXIV_MAX_RESULTS,
    days_back: int = ARXIV_DAYS_BACK,
) -> dict[str, int]:
    """Fetch all configured categories sequentially."""
    totals = {
        "fetched": 0,
        "inserted": 0,
        "duplicates_skipped": 0,
        "failed": 0,
    }
    run_started = time.perf_counter()

    logger.info(
        "event=arxiv_ingest_start categories=%s max_results=%d days_back=%d",
        ",".join(categories),
        max_results,
        days_back,
    )

    headers = {"User-Agent": ARXIV_USER_AGENT}

    # loop to ingest each arxhiv category one by one
    with httpx.Client(timeout=30.0, headers=headers) as client:
        for i, category in enumerate(categories):
            if i > 0:
                time.sleep(ARXIV_REQUEST_DELAY_SEC)
            counts = ingest_category(db, client, category, max_results, days_back)
            for key in totals:
                totals[key] += counts.get(key, 0)

    duration = time.perf_counter() - run_started
    logger.info(
        "event=arxiv_ingest_complete fetched=%d inserted=%d duplicates_skipped=%d "
        "failed=%d duration_sec=%.2f",
        totals["fetched"],
        totals["inserted"],
        totals["duplicates_skipped"],
        totals["failed"],
        duration,
    )
    return totals


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is not set")

    _, db = get_db()
    try:
        ingest_arxiv(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
