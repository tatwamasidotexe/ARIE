"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getProblem } from "@/lib/api";
import type { ProblemWithReport } from "@/lib/api";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

export default function TrendDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const [problem, setProblem] = useState<ProblemWithReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getProblem(id)
      .then(setProblem)
      .catch(() => setProblem(null))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 rounded bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse" />
        <div className="h-32 rounded-xl bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse" />
      </div>
    );
  }

  if (!problem) {
    return (
      <div className="rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-4">
        <p className="font-medium">Problem not found</p>
        <Link href="/" className="text-emerald-600 hover:underline mt-2 inline-block">
          ← Back to trends
        </Link>
      </div>
    );
  }

  const report = problem.latest_report;

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="text-sm text-zinc-500 hover:text-emerald-600 dark:hover:text-emerald-400"
      >
        ← Back to trends
      </Link>
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          {problem.summary}
        </h1>
        <div className="mt-2 flex items-center gap-2 text-sm text-zinc-500">
          <span>Frequency: {problem.frequency_score.toFixed(1)}</span>
          <span>•</span>
          <span>{problem.status}</span>
        </div>
      </div>

      {report ? (
        <div className="space-y-6">
          <Link
            href={`/reports/${report.id}`}
            className="block rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
          >
            <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
              Latest Report
            </h2>
            <p className="mt-2 text-zinc-600 dark:text-zinc-400 line-clamp-2">
              {report.problem_summary}
            </p>
            <div className="mt-3">
              <ConfidenceBadge score={report.confidence_score} />
            </div>
          </Link>
        </div>
      ) : (
        <p className="text-zinc-500">No report generated yet.</p>
      )}
    </div>
  );
}
