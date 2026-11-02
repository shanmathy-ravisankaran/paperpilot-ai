"use client";

import Link from "next/link";
import { ArrowUpRight, BookOpenText, FileSearch, FlaskConical, Layers3 } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchPapers } from "@/lib/api";
import { HealthStatus } from "@/components/health-status";

const actions = [
  { href: "/library", title: "Paper Library", detail: "Upload, label, and inspect local PDF evidence.", icon: BookOpenText },
  { href: "/ask", title: "Ask PaperPilot", detail: "Ask evidence-bounded questions and open source passages.", icon: FileSearch },
  { href: "/research", title: "Compare & Gaps", detail: "Compare selected papers or explore supported gaps.", icon: Layers3 },
  { href: "/evaluation", title: "Evaluation Lab", detail: "Review measured retrieval runs and regressions.", icon: FlaskConical },
];

export function DashboardOverview() {
  const [paperCount, setPaperCount] = useState<number | null>(null);
  useEffect(() => { fetchPapers().then((papers) => setPaperCount(papers.length)).catch(() => setPaperCount(null)); }, []);
  return <div className="content dashboard-content">
    <div className="eyebrow"><span className="eyebrow-dot" /> YOUR RESEARCH WORKSPACE</div>
    <h1>Research, with <em>clarity.</em></h1>
    <p className="intro">A local AI research workspace that connects answers, comparisons, and evaluations to inspectable evidence.</p>
    <div className="overview-grid">
      <section className="hero-card"><div className="hero-top"><span className="hero-kicker">EVIDENCE-GROUNDED RESEARCH</span><span className="milestone">LOCAL WORKSPACE</span></div><h2>Start with your source material.</h2><p>Upload text-based PDFs, inspect page-aware retrieval, and use local inference only when you want it.</p><div className="hero-bottom"><span><span className="small-dot" /> {paperCount === null ? "Checking local library…" : `${paperCount} indexed ${paperCount === 1 ? "paper" : "papers"}`}</span><Link href="/library">Open library <ArrowUpRight size={15} /></Link></div></section>
      <div className="overview-status"><HealthStatus /></div>
    </div>
    <div className="section-heading"><div><span className="section-kicker">QUICK ACTIONS</span><h2>Choose a focused workspace</h2></div></div>
    <div className="module-grid">{actions.map(({ href, title, detail, icon: Icon }) => <Link href={href} className="module" key={href}><div className="module-icon"><Icon size={20} /></div><div><h3>{title}</h3><p>{detail}</p></div><span className="available">Open</span></Link>)}</div>
    <p className="overview-note">Source passages are retrieved evidence. Generated answers and cross-paper interpretations remain AI-assisted and should be checked against their cited passages.</p>
    <footer>PaperPilot AI · Evidence before answers · Built with Next.js + FastAPI</footer>
  </div>;
}
