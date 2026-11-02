import type { Metadata } from "next";
import "./globals.css";
import { WorkspaceShell } from "@/components/workspace-shell";

export const metadata: Metadata = {
  title: "PaperPilot AI | Research Intelligence",
  description: "Evidence-grounded research intelligence, built with Next.js and FastAPI.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><WorkspaceShell>{children}</WorkspaceShell></body>
    </html>
  );
}
