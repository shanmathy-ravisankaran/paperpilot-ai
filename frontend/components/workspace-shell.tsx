"use client";

import Link from "next/link";
import { BookOpenText, FileSearch, FlaskConical, GitBranch, Layers3 } from "lucide-react";
import { usePathname } from "next/navigation";

const navigation = [
  { href: "/", label: "Overview", icon: GitBranch },
  { href: "/library", label: "Paper Library", icon: BookOpenText },
  { href: "/ask", label: "Ask PaperPilot", icon: FileSearch },
  { href: "/research", label: "Compare & Gaps", icon: Layers3 },
  { href: "/evaluation", label: "Evaluation Lab", icon: FlaskConical },
];

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const current = navigation.find((item) => item.href === pathname)?.label ?? "Workspace";
  return <main className="shell">
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="PaperPilot AI overview"><div className="brand-mark"><BookOpenText size={21} /></div><span>PaperPilot<span className="brand-ai">AI</span></span></Link>
      <nav className="sidebar-group" aria-label="Workspace">
        <span className="sidebar-label">WORKSPACE</span>
        {navigation.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={pathname === href ? "nav-active" : "nav-link"} aria-current={pathname === href ? "page" : undefined}><Icon size={17} /> {label}</Link>)}
      </nav>
      <div className="sidebar-footer">RESEARCH INTELLIGENCE<br /><span>Local-first research workspace</span></div>
    </aside>
    <div className="main-content"><header className="topbar"><span>Workspace / {current}</span><span className="build-tag">LOCAL-FIRST RESEARCH</span></header>{children}</div>
  </main>;
}
