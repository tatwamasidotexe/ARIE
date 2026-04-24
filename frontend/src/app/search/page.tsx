"use client";

import { useState } from "react";
import Link from "next/link";
import { searchInsights } from "@/lib/api";
import type { InsightReport } from "@/lib/api";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InsightReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const data = await searchInsights(query.trim());
      setResults(data);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        Search Problems
      </h1>

      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. API rate limit, deployment failures..."
          className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-2.5 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 px-5 py-2.5 font-medium text-white transition-colors"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {searched && (
        <>
          {loading ? (
            <div className="grid gap-3">
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className="h-20 rounded-xl bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse"
                />
              ))}
            </div>
          ) : results.length === 0 ? (
            <p className="text-zinc-500">No matching insights found.</p>
          ) : (
            <div className="grid gap-3">
              {results.map((r) => (
                <Link
                  key={r.id}
                  href={`/reports/${r.id}`}
                  className="block rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
                >
                  <p className="font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2">
                    {r.problem_summary}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <ConfidenceBadge score={r.confidence_score} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
