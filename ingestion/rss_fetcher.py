"""RSS feed fetcher - fetches blog posts and publishes to Redis Stream."""
import uuid
from datetime import datetime

import feedparser
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ingestion.config import DATABASE_URL, REDIS_URL, STREAM_NEW_POST

import requests

FEEDS = [
    "https://hnrss.org/frontpage",
    "https://news.ycombinator.com/rss",
    "https://openai.com/blog/rss.xml",
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://stackoverflow.com/feeds",
]


def get_db():
    engine = create_engine(DATABASE_URL)
    return sessionmaker(bind=engine)()


def fetch_feed(url: str):
    """Parse RSS feed and return entries."""
    try:
        d = feedparser.parse(url, agent="ARIE/1.0")
        entries = []
        for e in d.entries[:20]:
            link = e.get("link", "")
            comments_link = e.get("comments", "")
            hn_comments = ""

            if comments_link and "news.ycombinator.com/item?id=" in comments_link:
                try:
                    item_id = comments_link.split("id=")[-1]
                    hn_comments = fetch_hn_comments(item_id)
                except Exception:
                    pass
            base_content = e.get("summary", "") or e.get("description", "") or ""
            full_content = base_content + "\n\n" + hn_comments if hn_comments else base_content
            entries.append(
                {
                    "external_id": e.get("id") or link or str(uuid.uuid4()),
                    "title": e.get("title", ""),
                    "content": full_content,
                    "url": link,
                    "author": e.get("author"),
                    "created_at": None,
                }
            )
        return entries
    except Exception as ex:
        print(f"Error fetching {url}: {ex}")
        return []

def fetch_hn_comments(item_id: str, max_comments: int = 20) -> str:
    """Fetch top-level HN comments and return as text."""
    try:
        url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
        data = requests.get(url, timeout=5).json()

        if not data or "kids" not in data:
            return ""

        comments = []
        for cid in data["kids"][:max_comments]:
            cdata = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{cid}.json",
                timeout=5
            ).json()

            if cdata and cdata.get("text"):
                comments.append(cdata["text"])

        return "\n\n".join(comments)

    except Exception as e:
        print(f"HN comment fetch error: {e}")
        return ""

def store_and_publish(db, redis_client, entries, source: str = "rss"):
    """Insert entries and publish events."""
    for e in entries:
        external_id = f"{source}:{e['external_id'][:200]}"
        try:
            db.execute(
                text(
                    """
                INSERT INTO raw_posts (id, source, external_id, title, content, url, author, metadata)
                VALUES (:id, :source, :external_id, :title, :content, :url, :author, '{}'::jsonb)
                ON CONFLICT (external_id) DO NOTHING
                """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "source": source,
                    "external_id": external_id,
                    "title": e["title"][:2000],
                    "content": (e.get("content") or "")[:50000],
                    "url": e.get("url"),
                    "author": e.get("author"),
                },
            )
            db.commit()
            row = db.execute(
                text("SELECT id FROM raw_posts WHERE external_id = :eid"),
                {"eid": external_id},
            ).fetchone()
            if row:
                redis_client.xadd(
                    STREAM_NEW_POST,
                    {"raw_post_id": str(row[0]), "source": source},
                    maxlen=10000,
                )
        except Exception as err:
            db.rollback()
            print(f"Error storing {external_id}: {err}")


def main():
    db = get_db()
    r = redis.from_url(REDIS_URL)
    for url in FEEDS:
        entries = fetch_feed(url)
        print(f"Fetched {len(entries)} raw entries from {url}")
        if entries:
            source = ''
            if "stackoverflow.com" in url:
                source = "stackoverflow"
            elif "ycombinator" in url or "hnrss" in url:
                source = "hn"
            elif "openai.com" in url:
                source = "openai"
            elif "aws.amazon.com" in url:
                source = "aws"
            else:
                source = "rss"
            store_and_publish(db, r, entries, source=source)
            print(f"Fetched {len(entries)} entries from {url[:50]}...")
    db.close()


if __name__ == "__main__":
    main()

