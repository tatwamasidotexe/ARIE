"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchTrends } from "@/lib/api";
import type { Problem } from "@/lib/api";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

export default function Home() {
  const [trends, setTrends] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTrends({ limit: 15 })
      .then(setTrends)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Trending Issues
        </h1>
        <div className="grid gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 rounded-xl bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-4 text-red-700 dark:text-red-300">
        <p className="font-medium">Failed to load trends</p>
        <p className="text-sm mt-1">{error}</p>
        <p className="text-sm mt-2">
          Ensure the backend is running at{" "}
          <code className="bg-red-100 dark:bg-red-900/40 px-1 rounded">
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
          </code>
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Trending Issues
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400 mt-1">
          Emerging problems ranked by frequency across Reddit, HackerNews, and
          RSS feeds
        </p>
      </div>

      {trends.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-12 text-center text-zinc-500">
          No trending issues yet. Run the ingestion service and worker to
          populate data.
        </div>
      ) : (
        <div className="grid gap-3">
          {trends.map((p) => (
            <Link
              key={p.id}
              href={`/trends/${p.id}`}
              className="block rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 hover:border-emerald-300 dark:hover:border-emerald-700 hover:shadow-md transition-all"
            >
              <p className="font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2">
                {p.summary}
              </p>
              <div className="mt-2 flex items-center gap-2 text-sm text-zinc-500">
                <span>Frequency: {p.frequency_score.toFixed(1)}</span>
                <span>•</span>
                <span>{p.status}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
