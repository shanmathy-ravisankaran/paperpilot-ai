"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { FileText, LoaderCircle, Search, Upload, XCircle } from "lucide-react";
import { fetchPapers, Paper, Passage, searchPassages, uploadPdf } from "@/lib/api";

export function PaperLibrary() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [state, setState] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState(""); const [results, setResults] = useState<Passage[]>([]);
  const [searching, setSearching] = useState(false);
  useEffect(() => { fetchPapers().then(setPapers).catch(() => setMessage("The paper library is unavailable. Start the local API to load it.")); }, []);
  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { setState("error"); setMessage("Choose a PDF file to upload."); return; }
    if (file.size > 25 * 1024 * 1024) { setState("error"); setMessage("This PDF exceeds the 25 MB upload limit."); return; }
    setState("uploading"); setMessage("Reading, chunking, and indexing your paper locally…");
    try { const paper = await uploadPdf(file); setPapers((items) => [paper, ...items.filter((item) => item.id !== paper.id)]); setState("success"); setMessage(`Indexed “${paper.title}” — ${paper.chunk_count} passages across ${paper.page_count} pages.`); }
    catch (error) { setState("error"); setMessage(error instanceof Error ? error.message : "Upload failed. Please try again."); }
  }
  async function onSearch(event: FormEvent) {
    event.preventDefault(); if (query.trim().length < 2) return;
    setSearching(true); try { setResults(await searchPassages(query.trim())); } catch (error) { setMessage(error instanceof Error ? error.message : "Search failed."); setState("error"); } finally { setSearching(false); }
  }
  return <section id="library" className="library-panel" aria-labelledby="library-heading">
    <div className="library-header"><div><span className="section-kicker">MILESTONE 02 · LOCAL RETRIEVAL</span><h2 id="library-heading">Your paper library</h2><p>Upload text-based PDFs up to 25 MB. Search returns retrieved source passages only—no generated claims or invented citations.</p></div><label className="upload-button"><Upload size={16} /> Upload PDF<input type="file" accept="application/pdf,.pdf" onChange={onUpload} /></label></div>
    {state !== "idle" && <div className={`ingestion-state ${state}`} role={state === "error" ? "alert" : "status"}>{state === "uploading" ? <LoaderCircle className="spin" size={17} /> : state === "error" ? <XCircle size={17} /> : <FileText size={17} />}<span>{message}</span></div>}
    <form className="search-form" onSubmit={onSearch}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your indexed papers…" aria-label="Search indexed papers" /><button disabled={searching || query.trim().length < 2}>{searching ? "Searching…" : "Search"}</button></form>
    {results.length > 0 && <div className="passages" aria-live="polite">{results.map((result) => <article className="passage" key={result.chunk_id}><div className="passage-meta"><span>{result.title}</span><span>p. {result.page} · {result.section}</span><span>{Math.round(result.score * 100)}% similarity</span></div><p>{result.text}</p></article>)}</div>}
    <div className="paper-list">{papers.length ? papers.map((paper) => <article className="paper-row" key={paper.id}><FileText size={19} /><div><h3>{paper.title}</h3><p>{paper.author ?? paper.filename} · {paper.page_count} pages · {paper.chunk_count} passages</p></div><span>Indexed</span></article>) : <div className="empty-library"><FileText size={20} /><span>No papers indexed yet. Your PDFs remain on this machine.</span></div>}</div>
  </section>;
}
