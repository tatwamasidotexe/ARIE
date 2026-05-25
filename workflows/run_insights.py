"""Stage 3: run LangGraph insight pipeline on embedded documents."""
import argparse
import json
import logging
import uuid

from sqlalchemy import text

from agents.graph import run_pipeline
from database.db import get_db

logger = logging.getLogger(__name__)

UNPROCESSED_QUERY = """
    SELECT r.id, r.title, r.content, d.id AS doc_id
    FROM raw_posts r
    INNER JOIN documents d ON d.raw_post_id = r.id
    WHERE NOT EXISTS (
        SELECT 1 FROM problems p WHERE d.id = ANY(p.document_ids)
    )
    ORDER BY r.fetched_at
"""

ALL_EMBEDDED_QUERY = """
    SELECT r.id, r.title, r.content, d.id AS doc_id
    FROM raw_posts r
    INNER JOIN documents d ON d.raw_post_id = r.id
    ORDER BY r.fetched_at
"""

def fetch_posts_for_insights(db, force: bool) -> list[dict]:
    query = ALL_EMBEDDED_QUERY if force else UNPROCESSED_QUERY
    rows = db.execute(text(query)).fetchall()
    return [
        {
            "raw_post_id": str(row[0]),
            "title": row[1] or "",
            "content": row[2] or "",
            "doc_id": str(row[3]),
        }
        for row in rows
    ]


def clear_existing_reports(db, doc_id: str) -> None:
    """Remove prior problems and reports for a document (--force)."""
    problem_rows = db.execute(
        text("SELECT id FROM problems WHERE :doc_id = ANY(document_ids)"),
        {"doc_id": doc_id},
    ).fetchall()
    problem_ids = [str(row[0]) for row in problem_rows]
    if not problem_ids:
        return

    for problem_id in problem_ids:
        db.execute(
            text("DELETE FROM insight_reports WHERE problem_id = :pid"),
            {"pid": problem_id},
        )
    db.execute(
        text("DELETE FROM problems WHERE :doc_id = ANY(document_ids)"),
        {"doc_id": doc_id},
    )
    db.commit()
    logger.debug("Cleared %d existing problem(s) for doc_id=%s", len(problem_ids), doc_id)


def store_pipeline_report(db, doc_id: str, report: dict) -> None:
    """Persist problem and insight report from pipeline output."""
    problem_id = str(uuid.uuid4())
    db.execute(
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
    db.execute(
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
    db.commit()


def run_insight_pass(db, force: bool) -> dict[str, int]:
    posts = fetch_posts_for_insights(db, force=force)
    total = len(posts)
    succeeded = 0
    failed = 0
    skipped_empty = 0

    mode = "force-regenerate" if force else "incremental"
    logger.info("=== STAGE 3: RUN INSIGHT PIPELINE (%s, %d posts) ===", mode, total)

    if total == 0:
        logger.info("No embedded documents pending insight generation")
        return {"total": 0, "succeeded": 0, "failed": 0}

    for i, post in enumerate(posts, start=1):
        raw_post_id = post["raw_post_id"]
        doc_id = post["doc_id"]
        title = post["title"]
        content = post["content"] or title

        try:
            if force:
                clear_existing_reports(db, doc_id)

            logger.info("Running pipeline %d/%d: %s", i, total, title[:80])
            report = run_pipeline(raw_post_id, title, content)
            if not report:
                skipped_empty += 1
                logger.warning(
                    "Pipeline returned empty report for raw_post_id=%s",
                    raw_post_id,
                )
                continue

            store_pipeline_report(db, doc_id, report)
            succeeded += 1
            logger.info(
                "Stored report %d/%d: %s",
                i,
                total,
                report.get("problem_summary", "")[:80],
            )
        except Exception as exc:
            db.rollback()
            failed += 1
            logger.error(
                "Pipeline failed %d/%d for raw_post_id=%s: %s",
                i,
                total,
                raw_post_id,
                exc,
            )

    logger.info(
        "Insight generation complete — processed=%d succeeded=%d failed=%d empty=%d",
        total,
        succeeded,
        failed,
        skipped_empty,
    )
    return {"total": total, "succeeded": succeeded, "failed": failed}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LangGraph insight pipeline on embedded documents.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate insights for all embedded documents (replaces existing reports).",
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
        run_insight_pass(db, force=args.force)
    finally:
        db.close()


if __name__ == "__main__":
    main()
