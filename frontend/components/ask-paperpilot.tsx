"use client";
import { FormEvent, useEffect, useState } from "react";
import { BookOpenCheck, ChevronRight, LoaderCircle, Send, Sparkles } from "lucide-react";
import { askPaperPilot, AskResponse, fetchPapers, fetchSummary, Paper, SummaryResponse } from "@/lib/api";

export function AskPaperPilot() {
  const [papers, setPapers] = useState<Paper[]>([]); const [paperId, setPaperId] = useState(""); const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null); const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  useEffect(() => { fetchPapers().then((items) => { setPapers(items); if (items[0]) setPaperId(items[0].id); }).catch(() => setError("Start the local API to load papers.")); }, []);
  async function ask(event: FormEvent) { event.preventDefault(); if (question.trim().length < 2) return; setLoading(true); setError(""); setSummary(null); try { setAnswer(await askPaperPilot(question.trim(), paperId || undefined)); } catch (e) { setError(e instanceof Error ? e.message : "The answer request failed."); } finally { setLoading(false); } }
  async function summarize() { if (!paperId) return; setLoading(true); setError(""); setAnswer(null); try { setSummary(await fetchSummary(paperId)); } catch (e) { setError(e instanceof Error ? e.message : "The summary request failed."); } finally { setLoading(false); } }
  const sources = answer?.sources ?? summary?.sources ?? [];
  return <section id="ask" className="ask-panel" aria-labelledby="ask-heading"><div className="ask-title"><div><span className="section-kicker">MILESTONE 03 · GROUNDED Q&A</span><h2 id="ask-heading">Ask PaperPilot</h2><p>Answers are constrained to retrieved evidence and show their exact source passages.</p></div><Sparkles size={23} /></div>
    <form onSubmit={ask} className="ask-form"><select value={paperId} onChange={(e) => setPaperId(e.target.value)} aria-label="Limit question to a paper"><option value="">All indexed papers</option>{papers.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select><div className="ask-input"><input value={question} maxLength={1000} onChange={(e) => setQuestion(e.target.value)} placeholder="What does this research find?" /><button disabled={loading || question.trim().length < 2}>{loading ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}</button></div></form>
    {paperId && <button className="summary-button" onClick={summarize} disabled={loading}><BookOpenCheck size={15} /> Create structured summary</button>}
    {error && <p className="ask-error">{error}</p>}
    {answer && <article className="answer-card"><span className="answer-label">EVIDENCE-GROUNDED ANSWER</span><p>{answer.answer}</p></article>}
    {summary && <div className="summary-grid">{Object.entries(summary.sections).map(([name, value]) => <article key={name}><h3>{name}</h3><p>{value.text}</p>{value.not_stated && <span>Not stated</span>}</article>)}</div>}
    {sources.length > 0 && <div className="sources"><h3>Evidence</h3>{sources.map((source) => <a key={source.citation_id} href={`#source-${source.citation_id}`} className="source-link"><span>[{source.citation_id}]</span> {source.title}, p. {source.page} <ChevronRight size={14} /></a>)}{sources.map((source) => <article id={`source-${source.citation_id}`} className="source-preview" key={`${source.citation_id}-preview`}><b>[{source.citation_id}] {source.title} · p. {source.page}</b><p>{source.text}</p></article>)}</div>}
  </section>;
}
