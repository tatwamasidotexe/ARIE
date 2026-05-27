"""Analyze raw_posts token counts for the configured embedding model."""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from transformers import AutoTokenizer

from agents.config import HF_EMBEDDING_MODEL
from database.db import get_db

DEFAULT_CONTEXT_WINDOW = 512

RAW_POSTS_QUERY = """
    SELECT id, source, title, content, url
    FROM raw_posts
    ORDER BY fetched_at
"""


@dataclass
class TokenStats:
    raw_post_id: str
    source: str
    title: str
    url: str | None
    token_count: int


def build_embedding_text(title: str, content: str) -> str:
    """Match the text format used when creating document embeddings."""
    clean_title = title or ""
    clean_content = content or clean_title
    return f"{clean_title}\n\n{clean_content}"


def fetch_raw_posts(db) -> list[dict]:
    rows = db.execute(text(RAW_POSTS_QUERY)).fetchall()
    return [
        {
            "raw_post_id": str(row[0]),
            "source": row[1] or "",
            "title": row[2] or "",
            "content": row[3] or "",
            "url": row[4],
        }
        for row in rows
    ]


def count_tokens(tokenizer, text_to_count: str) -> int:
    tokens = tokenizer(
        text_to_count,
        truncation=False,
        add_special_tokens=True,
        verbose=False,
    )
    return len(tokens["input_ids"])


def analyze_posts(tokenizer, posts: list[dict]) -> list[TokenStats]:
    stats = []
    for post in posts:
        token_count = count_tokens(
            tokenizer,
            build_embedding_text(post["title"], post["content"]),
        )
        stats.append(
            TokenStats(
                raw_post_id=post["raw_post_id"],
                source=post["source"],
                title=post["title"],
                url=post["url"],
                token_count=token_count,
            )
        )
    return stats


def print_summary(stats: list[TokenStats], context_window: int, show_all_over_limit: bool) -> None:
    if not stats:
        print("No raw_posts found.")
        return

    token_counts = [entry.token_count for entry in stats]
    over_limit = [entry for entry in stats if entry.token_count > context_window]

    print("Token count summary")
    print(f"- rows analyzed: {len(stats)}")
    print(f"- embedding context window: {context_window}")
    print(f"- average tokens: {mean(token_counts):.2f}")
    print(f"- min tokens: {min(token_counts)}")
    print(f"- max tokens: {max(token_counts)}")
    print(f"- entries over {context_window}: {len(over_limit)}")

    if not over_limit:
        return

    print(f"\nEntries exceeding {context_window} tokens:")
    entries_to_print = over_limit if show_all_over_limit else over_limit[:25]
    for entry in sorted(entries_to_print, key=lambda item: item.token_count, reverse=True):
        title = entry.title.replace("\n", " ").strip()
        if len(title) > 100:
            title = f"{title[:97]}..."
        print(
            f"- {entry.token_count} tokens | {entry.source} | "
            f"{entry.raw_post_id} | {title}"
        )
        if entry.url:
            print(f"  {entry.url}")

    remaining = len(over_limit) - len(entries_to_print)
    if remaining > 0:
        print(f"\n...and {remaining} more. Re-run with --show-all-over-limit to list every row.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute token counts for raw_posts before embedding.",
    )
    parser.add_argument(
        "--model",
        default=HF_EMBEDDING_MODEL,
        help=f"Tokenizer/model name to use. Defaults to HF_EMBEDDING_MODEL ({HF_EMBEDDING_MODEL}).",
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=DEFAULT_CONTEXT_WINDOW,
        help=f"Token limit to flag. Defaults to {DEFAULT_CONTEXT_WINDOW}.",
    )
    parser.add_argument(
        "--show-all-over-limit",
        action="store_true",
        help="Print every over-limit raw_post instead of the first 25.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    db = get_db()
    try:
        posts = fetch_raw_posts(db)
        stats = analyze_posts(tokenizer, posts)
        print_summary(stats, args.context_window, args.show_all_over_limit)
    finally:
        db.close()


if __name__ == "__main__":
    main()
