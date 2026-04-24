const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface InsightReport {
  id: string;
  problem_id: string;
  problem_summary: string;
  evidence: string[];
  root_causes: string[];
  solutions: string[];
  confidence_score: number;
  sources: { title?: string; source?: string }[];
  created_at: string;
}

export interface Problem {
  id: string;
  summary: string;
  frequency_score: number;
  status: string;
  first_detected_at: string;
  last_updated_at: string;
}

export interface ProblemWithReport extends Problem {
  latest_report?: InsightReport;
}

export async function fetchInsights(params?: {
  limit?: number;
  min_confidence?: number;
}): Promise<InsightReport[]> {
  const search = new URLSearchParams(params as Record<string, string>).toString();
  const res = await fetch(`${API_BASE}/insights?${search}`);
  if (!res.ok) throw new Error("Failed to fetch insights");
  return res.json();
}

export async function searchInsights(q: string, limit = 20): Promise<InsightReport[]> {
  const res = await fetch(
    `${API_BASE}/insights/search?q=${encodeURIComponent(q)}&limit=${limit}`
  );
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function getInsight(id: string): Promise<InsightReport> {
  const res = await fetch(`${API_BASE}/insights/${id}`);
  if (!res.ok) throw new Error("Insight not found");
  return res.json();
}

export async function fetchTrends(params?: {
  limit?: number;
  min_frequency?: number;
}): Promise<Problem[]> {
  const search = new URLSearchParams(params as Record<string, string>).toString();
  const res = await fetch(`${API_BASE}/trends?${search}`);
  if (!res.ok) throw new Error("Failed to fetch trends");
  return res.json();
}

export async function getProblem(id: string): Promise<ProblemWithReport> {
  const res = await fetch(`${API_BASE}/trends/${id}`);
  if (!res.ok) throw new Error("Problem not found");
  return res.json();
}
