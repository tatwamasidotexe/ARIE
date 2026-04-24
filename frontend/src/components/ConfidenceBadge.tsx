export function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const variant =
    pct >= 70 ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" :
    pct >= 40 ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300" :
    "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variant}`}
    >
      {pct}% confidence
    </span>
  );
}
