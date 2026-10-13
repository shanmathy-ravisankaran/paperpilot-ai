export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  timestamp: string;
};
export type Paper = { id: string; title: string; author: string | null; filename: string; page_count: number; chunk_count: number; indexed_at: string };
export type Passage = { text: string; score: number; paper_id: string; title: string; page: number; section: string; chunk_id: string };
export type Citation = Passage & { citation_id: string };
export type AskResponse = { answer: string; citations: string[]; sources: Citation[] };
export type SummaryResponse = { sections: Record<string, { text: string; citations: string[]; not_stated: boolean }>; sources: Citation[] };
export type Comparison = { papers: Array<{ paper_id: string; [key: string]: unknown }>; relationships: Array<{ classification: string; explanation: string; citations: string[]; limitation: string }>; sources: Citation[] };
export type Gaps = { gaps: Array<{ title: string; category: string; explanation: string; citations: string[]; why_it_might_matter: string; follow_up_question: string; author_stated: boolean; label: string }>; limitation: string; sources: Citation[] };

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function localFetch(input: RequestInfo | URL, init?: RequestInit, timeoutMs = 20_000): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The local request timed out. Confirm that the API and Ollama are running, then try again.");
    }
    throw new Error("The local API is unavailable. Start the backend and try again.");
  } finally {
    window.clearTimeout(timer);
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`API returned HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (
    !data || typeof data !== "object" ||
    !("status" in data) || data.status !== "ok" ||
    !("service" in data) || typeof data.service !== "string" ||
    !("version" in data) || typeof data.version !== "string" ||
    !("timestamp" in data) || typeof data.timestamp !== "string"
  ) throw new Error("Unexpected health response");
  return data as HealthResponse;
}

async function apiError(response: Response): Promise<never> {
  const body: unknown = await response.json().catch(() => null);
  const detail = body && typeof body === "object" && "detail" in body && typeof body.detail === "string" ? body.detail : `API returned HTTP ${response.status}`;
  throw new Error(detail);
}
export async function fetchPapers(): Promise<Paper[]> {
  const response = await fetch(`${API_BASE_URL}/papers`, { cache: "no-store" });
  if (!response.ok) return apiError(response);
  return response.json() as Promise<Paper[]>;
}
export async function uploadPdf(file: File): Promise<Paper> {
  const form = new FormData(); form.append("file", file);
  const response = await localFetch(`${API_BASE_URL}/papers/upload`, { method: "POST", body: form }, 90_000);
  if (!response.ok) return apiError(response);
  return response.json() as Promise<Paper>;
}
export async function searchPassages(query: string): Promise<Passage[]> {
  const response = await fetch(`${API_BASE_URL}/papers/search?query=${encodeURIComponent(query)}`, { cache: "no-store" });
  if (!response.ok) return apiError(response);
  const body = await response.json() as { results: Passage[] };
  return body.results;
}
export async function askPaperPilot(question: string, paper_id?: string): Promise<AskResponse> {
  const response = await localFetch(`${API_BASE_URL}/qa/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, paper_id }) }, 120_000);
  if (!response.ok) return apiError(response);
  return response.json() as Promise<AskResponse>;
}
export async function fetchSummary(paperId: string): Promise<SummaryResponse> {
  const response = await localFetch(`${API_BASE_URL}/qa/papers/${paperId}/summary`, { method: "POST" }, 120_000);
  if (!response.ok) return apiError(response);
  return response.json() as Promise<SummaryResponse>;
}
async function research<T>(path: string, paper_ids: string[]): Promise<T> {
  const response = await localFetch(`${API_BASE_URL}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paper_ids }) }, 150_000);
  if (!response.ok) return apiError(response);
  return response.json() as Promise<T>;
}
export const comparePapers = (paperIds: string[]) => research<Comparison>("/research/compare", paperIds);
export const exploreGaps = (paperIds: string[]) => research<Gaps>("/research/gaps", paperIds);
export type EvaluationResult = { id: string; answerable: boolean; expected_pages: number[]; retrieved: Array<{ page: number }>; retrieval_latency_ms: number };
export type EvaluationRun = { run_id: string; timestamp: string; dataset_version: string; dataset_size: number; evaluated_retrieval_examples: number; answerable_denominator?: number; unanswerable_excluded_from_hit_metrics?: number; cross_paper_skipped?: number; embedding_model: string; llm_model: string; retrieval_config?: Record<string, string | number>; metrics: Record<string, number>; candidate_metrics?: Record<string, number>; results: EvaluationResult[]; candidate_results?: EvaluationResult[]; limitations: string[] };
export async function createEvaluationRun(): Promise<EvaluationRun> { const response = await localFetch(`${API_BASE_URL}/evaluation/runs`, { method: "POST" }, 120_000); if (!response.ok) return apiError(response); return response.json() as Promise<EvaluationRun>; }
export async function fetchEvaluationRuns(): Promise<EvaluationRun[]> { const response = await fetch(`${API_BASE_URL}/evaluation/runs`, { cache: "no-store" }); if (!response.ok) return apiError(response); return response.json() as Promise<EvaluationRun[]>; }
