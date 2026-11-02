"use client";

import { useEffect, useState } from "react";
import { BarChart3, LoaderCircle } from "lucide-react";
import { createEvaluationRun, EvaluationResult, EvaluationRun, fetchEvaluationRuns } from "@/lib/api";

const percentage = (value: number) => `${(value * 100).toFixed(2)}%`;
const valueFor = (name: string, value: number) => name === "mrr" ? value.toFixed(4) : name.includes("latency") ? `${value} ms` : percentage(value);
const label = (name: string) => name === "mrr" ? "MRR" : name.replaceAll("_", " ");
const pages = (row: EvaluationResult | undefined) => row ? row.retrieved.map((passage) => passage.page).join(", ") : "Not run";
const qualityMetrics = ["hit_at_1", "hit_at_3", "hit_at_5"];

export function EvaluationLab() {
  const [run, setRun] = useState<EvaluationRun | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  useEffect(() => { fetchEvaluationRuns().then((runs) => setRun(runs[0] ?? null)).catch(() => setError("Evaluation history is unavailable. Start the local API to load it.")); }, []);
  async function evaluate() { setLoading(true); setError(""); try { setRun(await createEvaluationRun()); } catch (error) { setError(error instanceof Error ? error.message : "Evaluation failed."); } finally { setLoading(false); } }
  return <section className="research-panel" aria-labelledby="evaluation-heading">
    <div className="ask-title"><div><span className="section-kicker">MEASURED RETRIEVAL EVALUATION</span><h2 id="evaluation-heading">Evaluation Lab</h2><p>Compare the production vector retriever with an experimental hybrid candidate on the same local index.</p></div><BarChart3 size={23} /></div>
    <div className="research-actions"><button onClick={evaluate} disabled={loading}>{loading ? <LoaderCircle className="spin" size={15} /> : <BarChart3 size={15} />} Run retrieval evaluation</button></div>
    {loading && <p className="selection-note" role="status">Embedding and ranking the versioned local dataset. This does not call an LLM.</p>}
    {error && <p className="ask-error" role="alert">{error}</p>}
    {run && <>
      <div className="evaluation-summary"><p><b>21</b> answerable single-paper prompts in ranking metrics</p><span>4 unanswerable exclusions · 5 cross-paper skips</span></div>
      <div className="metric-grid">{Object.entries(run.metrics).map(([name, value]) => <article key={name}><span>Vector baseline · {label(name)}</span><b>{valueFor(name, value)}</b></article>)}{run.candidate_metrics && Object.entries(run.candidate_metrics).map(([name, value]) => <article className={name !== "mean_retrieval_latency_ms" && value < (run.metrics[name] ?? value) ? "metric-regression" : ""} key={`candidate-${name}`}><span>Hybrid candidate · {label(name)}</span><b>{valueFor(name, value)}</b></article>)}</div>
      {run.candidate_metrics && <div className="retrieval-chart" role="img" aria-label="Bar chart comparing vector baseline and hybrid candidate Hit at 1, Hit at 3, and Hit at 5"><h3>Vector versus hybrid ranking</h3>{qualityMetrics.map((name) => <div className="chart-row" key={name}><span>{label(name)}</span><div><i className="vector-bar" style={{ width: percentage(run.metrics[name] ?? 0) }} /><i className="hybrid-bar" style={{ width: percentage(run.candidate_metrics?.[name] ?? 0) }} /></div><small>Vector {percentage(run.metrics[name] ?? 0)} · Hybrid {percentage(run.candidate_metrics?.[name] ?? 0)}</small></div>)}<p><span className="chart-key vector-key" /> Vector baseline <span className="chart-key hybrid-key" /> Hybrid candidate</p></div>}
      <p className="selection-note">The hybrid candidate regressed ranking on this small evaluation set and is not the production default. Dataset {run.dataset_version} · {run.embedding_model}.</p>
      <div className="comparison-scroll"><table><thead><tr><th>Question</th><th>Expected pages</th><th>Vector pages</th><th>Hybrid pages</th><th>Change</th></tr></thead><tbody>{run.results.map((row, index) => { const candidate = run.candidate_results?.[index]; const vectorHit = row.expected_pages.some((page) => row.retrieved.some((item) => item.page === page)); const candidateHit = candidate?.expected_pages.some((page) => candidate.retrieved.some((item) => item.page === page)); return <tr key={row.id}><td>{row.id}{!row.answerable && " (unanswerable)"}</td><td>{row.expected_pages.join(", ") || "Refusal"}</td><td>{pages(row)}</td><td>{pages(candidate)}</td><td>{candidateHit === undefined ? "Legacy run" : vectorHit === candidateHit ? "No page-hit change" : candidateHit ? "Improved" : "Regression"}</td></tr>; })}</tbody></table></div>
      <p className="selection-note">Retrieved evidence is not an AI answer. Page labels are manually verified evaluation aids; citation ownership or a page hit does not establish factual correctness. {run.limitations.join(" ")}</p>
    </>}
  </section>;
}
