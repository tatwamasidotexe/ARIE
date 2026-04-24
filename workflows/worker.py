"""
Redis Streams worker: new_post_event -> problem_detection -> research -> synthesis -> store_report
"""
import os
import sys
import uuid
import time
import json

# Add agents and ingestion to path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "agents"))

import redis
from sqlalchemy import create_engine, text

from workflows.config import REDIS_URL, STREAM_NEW_POST, CONSUMER_GROUP, CONSUMER_NAME, DATABASE_URL


def ensure_consumer_group(r: redis.Redis):
    try:
        r.xgroup_create(STREAM_NEW_POST, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def get_raw_post(engine, raw_post_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, source, title, content FROM raw_posts WHERE id = :id"),
            {"id": raw_post_id},
        ).fetchone()
    return row


def store_document_and_run_pipeline(engine, raw_post_id: str, source: str, title: str, content: str):
    """Import and run the agent pipeline. Documents are stored inside the pipeline."""
    from agents.embeddings import store_document
    from agents.graph import run_pipeline

    # Store document with embedding
    doc_id = store_document(raw_post_id, source, title, content or title)

    # Run LangGraph pipeline
    report = run_pipeline(raw_post_id, title, content or title)
    if not report:
        return

    # Insert problem and report
    problem_id = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO problems (id, summary, frequency_score, document_ids, status)
            VALUES (:id, :summary, 1.0, ARRAY[CAST(:doc_id AS uuid)], 'synthesized')
            """),
            {
                "id": problem_id,
                "summary": report.get("problem_summary", "Unknown"),
                "doc_id": doc_id,
            },
        )
        conn.execute(
            text("""
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
            """),
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
    print(f"Stored report for problem: {report.get('problem_summary', '')[:60]}...")


def _decode(v):
    if isinstance(v, bytes):
        return v.decode()
    return str(v) if v is not None else ""

def process_message(engine, msg_id: str, data: dict):
    raw_post_id = _decode(data.get(b"raw_post_id") or data.get("raw_post_id"))
    if not raw_post_id:
        return

    row = get_raw_post(engine, raw_post_id)
    if not row:
        print(f"Raw post not found: {raw_post_id}")
        return
    _id, src, title, content = row
    store_document_and_run_pipeline(engine, str(_id), src, title or "", content or "")


def run_worker():
    r = redis.from_url(REDIS_URL)
    engine = create_engine(DATABASE_URL)
    ensure_consumer_group(r)

    print("Worker started. Consuming from", STREAM_NEW_POST)
    while True:
        try:
            streams = r.xreadgroup(CONSUMER_GROUP, CONSUMER_NAME, {STREAM_NEW_POST: ">"}, count=1, block=5000)
            if not streams:
                continue
            for stream_name, messages in streams:
                for msg_id, data in messages:
                    try:
                        process_message(engine, msg_id, data)
                        r.xack(STREAM_NEW_POST, CONSUMER_GROUP, msg_id)
                    except Exception as e:
                        print(f"Error processing {msg_id}: {e}")
                        # Don't ack - let it retry or go to dead letter
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_worker()
