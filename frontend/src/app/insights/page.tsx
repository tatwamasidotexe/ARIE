"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchInsights } from "@/lib/api";
import type { InsightReport } from "@/lib/api";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchInsights({ limit: 30 })
      .then(setInsights)
      .catch(() => setInsights([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Reports</h1>
        <div className="grid gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        Insight Reports
      </h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Structured reports with evidence, root causes, and solutions
      </p>

      {insights.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-12 text-center text-zinc-500">
          No reports yet. Ingest data and run the worker to generate insights.
        </div>
      ) : (
        <div className="grid gap-3">
          {insights.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.id}`}
              className="block rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
            >
              <p className="font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2">
                {r.problem_summary}
              </p>
              <div className="mt-2 flex items-center justify-between text-sm">
                <ConfidenceBadge score={r.confidence_score} />
                <span className="text-zinc-500">
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
