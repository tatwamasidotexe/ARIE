"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getInsight } from "@/lib/api";
import type { InsightReport } from "@/lib/api";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

export default function ReportDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const [report, setReport] = useState<InsightReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getInsight(id)
      .then(setReport)
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 rounded bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse" />
        <div className="h-64 rounded-xl bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-4">
        <p className="font-medium">Report not found</p>
        <Link href="/insights" className="text-emerald-600 hover:underline mt-2 inline-block">
          ← Back to reports
        </Link>
      </div>
    );
  }

  const evidence = Array.isArray(report.evidence) ? report.evidence : [];
  const rootCauses = Array.isArray(report.root_causes) ? report.root_causes : [];
  const solutions = Array.isArray(report.solutions) ? report.solutions : [];
  const sources = Array.isArray(report.sources) ? report.sources : [];

  return (
    <div className="space-y-6">
      <Link
        href="/insights"
        className="text-sm text-zinc-500 hover:text-emerald-600 dark:hover:text-emerald-400"
      >
        ← Back to reports
      </Link>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800">
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
            {report.problem_summary}
          </h1>
          <div className="mt-3 flex items-center gap-2">
            <ConfidenceBadge score={report.confidence_score} />
            <span className="text-sm text-zinc-500">
              {new Date(report.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {evidence.length > 0 && (
            <section>
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Evidence
              </h2>
              <ul className="list-disc list-inside space-y-1 text-zinc-600 dark:text-zinc-400">
                {evidence.map((e, i) => (
                  <li key={i}>{typeof e === "string" ? e : JSON.stringify(e)}</li>
                ))}
              </ul>
            </section>
          )}

          {rootCauses.length > 0 && (
            <section>
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Root Causes
              </h2>
              <ul className="list-disc list-inside space-y-1 text-zinc-600 dark:text-zinc-400">
                {rootCauses.map((c, i) => (
                  <li key={i}>{typeof c === "string" ? c : JSON.stringify(c)}</li>
                ))}
              </ul>
            </section>
          )}

          {solutions.length > 0 && (
            <section>
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Solutions
              </h2>
              <ul className="list-disc list-inside space-y-1 text-zinc-600 dark:text-zinc-400">
                {solutions.map((s, i) => (
                  <li key={i}>{typeof s === "string" ? s : JSON.stringify(s)}</li>
                ))}
              </ul>
            </section>
          )}

          {sources.length > 0 && (
            <section>
              <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Sources
              </h2>
              <ul className="space-y-1 text-sm text-zinc-600 dark:text-zinc-400">
                {sources.map((s, i) => (
                  <li key={i}>
                    {typeof s === "object" && s !== null && "title" in s
                      ? (s as { title?: string; source?: string }).title ||
                        (s as { title?: string; source?: string }).source ||
                        JSON.stringify(s)
                      : String(s)}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
