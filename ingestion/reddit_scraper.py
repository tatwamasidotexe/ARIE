"""Reddit API scraper - fetches posts and publishes to Redis Stream."""
import os
import uuid
from datetime import datetime

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ingestion.config import (
    DATABASE_URL,
    REDIS_URL,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    STREAM_NEW_POST,
)

try:
    import praw
except ImportError:
    praw = None


def get_reddit():
    if not praw or not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return None
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def get_db():
    engine = create_engine(DATABASE_URL)
    return sessionmaker(bind=engine)()


def scrape_subreddit(reddit, subreddit_name: str, limit: int = 25):
    """Fetch hot posts from a subreddit."""
    if not reddit:
        return []
    sub = reddit.subreddit(subreddit_name)
    posts = []
    for post in sub.hot(limit=limit):
        posts.append(
            {
                "external_id": post.id,
                "title": post.title,
                "content": post.selftext or "",
                "url": f"https://reddit.com{post.permalink}",
                "author": str(post.author) if post.author else None,
                "created_at": datetime.fromtimestamp(post.created_utc).isoformat(),
                "metadata": {
                    "subreddit": subreddit_name,
                    "score": post.score,
                    "num_comments": post.num_comments,
                },
            }
        )
    return posts


def store_and_publish(db, redis_client, posts):
    """Insert posts into DB and publish events to Redis Stream."""
    for p in posts:
        external_id = f"reddit:{p['external_id']}"
        try:
            db.execute(
                text(
                    """
                INSERT INTO raw_posts (id, source, external_id, title, content, url, author, created_at, metadata)
                VALUES (:id, 'reddit', :external_id, :title, :content, :url, :author,
                        COALESCE((:created_at)::timestamptz, NOW()), :metadata::jsonb)
                ON CONFLICT (external_id) DO NOTHING
                """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "external_id": external_id,
                    "title": p["title"],
                    "content": p.get("content") or "",
                    "url": p.get("url"),
                    "author": p.get("author"),
                    "created_at": p.get("created_at"),
                    "metadata": str(p.get("metadata", {})),
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
                    {"raw_post_id": str(row[0]), "source": "reddit"},
                    maxlen=10000,
                )
        except Exception as e:
            db.rollback()
            print(f"Error storing post {external_id}: {e}")


def main():
    reddit = get_reddit()
    if not reddit:
        print("Reddit not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.")
        return
    db = get_db()
    r = redis.from_url(REDIS_URL)
    subreddits = ["programming", "technology", "MachineLearning", "Python"]
    for sub in subreddits:
        try:
            posts = scrape_subreddit(reddit, sub, limit=15)
            store_and_publish(db, r, posts)
            print(f"Scraped {len(posts)} posts from r/{sub}")
        except Exception as e:
            print(f"Error scraping r/{sub}: {e}")
    db.close()


if __name__ == "__main__":
    main()

