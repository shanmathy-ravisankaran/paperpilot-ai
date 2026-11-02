"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { FilePenLine, FileText, LoaderCircle, Search, Upload, XCircle } from "lucide-react";
import { fetchPapers, Paper, Passage, searchPassages, updatePaperDisplayTitle, uploadPdf } from "@/lib/api";

const paperName = (paper: Paper) => paper.display_title?.trim() || paper.title;

export function PaperLibrary() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [state, setState] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState(""); const [results, setResults] = useState<Passage[]>([]);
  const [searching, setSearching] = useState(false); const [editing, setEditing] = useState<string | null>(null); const [titleDraft, setTitleDraft] = useState("");
  useEffect(() => { fetchPapers().then(setPapers).catch(() => { setState("error"); setMessage("The paper library is unavailable. Start the local API to load it."); }); }, []);
  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { setState("error"); setMessage("Choose a PDF file to upload."); return; }
    if (file.size > 25 * 1024 * 1024) { setState("error"); setMessage("This PDF exceeds the 25 MB upload limit."); return; }
    setState("uploading"); setMessage("Reading, chunking, and indexing your paper locally…");
    try { const paper = await uploadPdf(file); setPapers((items) => [paper, ...items.filter((item) => item.id !== paper.id)]); setState("success"); setMessage(`Indexed “${paperName(paper)}” — ${paper.chunk_count} passages across ${paper.page_count} pages.`); }
    catch (error) { setState("error"); setMessage(error instanceof Error ? error.message : "Upload failed. Please try again."); }
  }
  async function onSearch(event: FormEvent) {
    event.preventDefault(); if (query.trim().length < 2) return;
    setSearching(true); try { setResults(await searchPassages(query.trim())); } catch (error) { setMessage(error instanceof Error ? error.message : "Search failed."); setState("error"); } finally { setSearching(false); }
  }
  async function saveTitle(paper: Paper) {
    try { const updated = await updatePaperDisplayTitle(paper.id, titleDraft.trim() || null); setPapers((items) => items.map((item) => item.id === updated.id ? updated : item)); setEditing(null); setState("success"); setMessage(updated.display_title ? "Display title saved locally. Original filename and source citations are unchanged." : "Display title reset to the extracted source title."); }
    catch (error) { setState("error"); setMessage(error instanceof Error ? error.message : "Could not save the display title."); }
  }
  return <section className="library-panel" aria-labelledby="library-heading">
    <div className="library-header"><div><span className="section-kicker">LOCAL PDF RETRIEVAL</span><h2 id="library-heading">Your paper library</h2><p>Upload text-based PDFs up to 25 MB. Search returns retrieved source passages only—no generated claims or invented citations.</p></div><label className="upload-button"><Upload size={16} /> Upload PDF<input type="file" accept="application/pdf,.pdf" onChange={onUpload} /></label></div>
    {state !== "idle" && <div className={`ingestion-state ${state}`} role={state === "error" ? "alert" : "status"}>{state === "uploading" ? <LoaderCircle className="spin" size={17} /> : state === "error" ? <XCircle size={17} /> : <FileText size={17} />}<span>{message}</span></div>}
    <form className="search-form" onSubmit={onSearch}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your indexed papers…" aria-label="Search indexed papers" /><button disabled={searching || query.trim().length < 2}>{searching ? "Searching…" : "Search"}</button></form>
    {results.length > 0 && <div className="passages" aria-live="polite">{results.map((result) => <article className="passage" key={result.chunk_id}><div className="passage-meta"><span>{result.title}</span><span>p. {result.page} · {result.section}</span><span>{Math.round(result.score * 100)}% similarity</span></div><p>{result.text}</p></article>)}</div>}
    <div className="paper-list">{papers.length ? papers.map((paper) => <article className="paper-row" key={paper.id}><FileText size={19} /><div>{editing === paper.id ? <form className="title-edit" onSubmit={(event) => { event.preventDefault(); void saveTitle(paper); }}><label htmlFor={`title-${paper.id}`}>Display title</label><input id={`title-${paper.id}`} value={titleDraft} maxLength={240} onChange={(event) => setTitleDraft(event.target.value)} autoFocus /><button>Save</button><button type="button" onClick={() => setEditing(null)}>Cancel</button></form> : <><h3>{paperName(paper)}</h3><p>{paper.author ?? paper.filename} · {paper.page_count} pages · {paper.chunk_count} passages</p>{paper.display_title && <small>Source title: {paper.title}</small>}</>}</div>{editing !== paper.id && <button className="title-button" onClick={() => { setEditing(paper.id); setTitleDraft(paper.display_title ?? paper.title); }} aria-label={`Edit display title for ${paperName(paper)}`}><FilePenLine size={15} /> Label</button>}<span>Indexed</span></article>) : <div className="empty-library"><FileText size={20} /><span>No papers indexed yet. Your PDFs remain on this machine.</span></div>}</div>
  </section>;
}
