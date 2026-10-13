import { ArrowUpRight, BookOpenText, Braces, FileSearch, FlaskConical, GitBranch, Layers3, Sparkles } from "lucide-react";
import { HealthStatus } from "@/components/health-status";
import { PaperLibrary } from "@/components/paper-library";
import { AskPaperPilot } from "@/components/ask-paperpilot";
import { ResearchWorkspace } from "@/components/research-workspace";
import { EvaluationLab } from "@/components/evaluation-lab";

const modules = [
  { title: "Paper library", subtitle: "PDF ingestion & metadata", icon: BookOpenText },
  { title: "Ask your papers", subtitle: "Grounded answers & citations", icon: FileSearch },
  { title: "Compare research", subtitle: "Cross-paper analysis", icon: Layers3 },
  { title: "Research gap explorer", subtitle: "Evidence-led insights", icon: Sparkles },
  { title: "Evaluation lab", subtitle: "Retrieval & answer quality", icon: FlaskConical },
  { title: "Developer API", subtitle: "Documented FastAPI endpoints", icon: Braces },
];

export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><BookOpenText size={21} /></div><span>PaperPilot<span className="brand-ai">AI</span></span></div>
        <nav className="sidebar-group" aria-label="Workspace"><span className="sidebar-label">WORKSPACE</span><a className="nav-active" href="#top"><GitBranch size={17} /> Overview</a><a className="nav-link" href="#library">Paper Library</a><a className="nav-link" href="#ask">Ask PaperPilot</a><a className="nav-link" href="#research">Compare & Gaps</a><a className="nav-link" href="#evaluation">Evaluation Lab</a></nav>
        <div className="sidebar-footer">RESEARCH INTELLIGENCE<br /><span>Local-first research workspace</span></div>
      </aside>
      <div className="main-content">
        <header className="topbar"><span>Workspace / Overview</span><span className="build-tag">LOCAL-FIRST · MILESTONES 1–5</span></header>
        <div className="content" id="top">
          <div className="eyebrow"><span className="eyebrow-dot" /> YOUR RESEARCH WORKSPACE</div>
          <h1>Research, with <em>clarity.</em></h1>
          <p className="intro">A modern AI research workspace designed to connect answers to evidence, compare findings, and uncover what deserves a closer look.</p>
          <div className="hero-card"><div className="hero-top"><span className="hero-kicker">EVIDENCE-GROUNDED RESEARCH</span><span className="milestone">LOCAL WORKSPACE</span></div><h2>Your research evidence, connected.</h2><p>Index local PDFs, inspect retrieved passages, ask grounded questions, compare selected papers, and review measured retrieval results. Every source reference identifies a paper and page.</p><div className="hero-bottom"><span><span className="small-dot" /> Local-first retrieval and inference</span><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Explore API docs <ArrowUpRight size={15} /></a></div></div>
          <PaperLibrary />
          <AskPaperPilot />
          <ResearchWorkspace />
          <EvaluationLab />
          <div className="section-heading"><div><span className="section-kicker">CAPABILITIES</span><h2>Built for evidence-led research</h2></div><span className="section-note">Available locally</span></div>
          <div className="module-grid">{modules.map(({ title, subtitle, icon: Icon }) => <div className="module" key={title}><div className="module-icon"><Icon size={20} /></div><div><h3>{title}</h3><p>{subtitle}</p></div><span className="available">Available</span></div>)}</div>
          <HealthStatus />
          <footer>PaperPilot AI · Evidence before answers · Built with Next.js + FastAPI</footer>
        </div>
      </div>
    </main>
  );
}
