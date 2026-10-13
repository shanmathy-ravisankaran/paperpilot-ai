"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, CircleAlert, RefreshCw } from "lucide-react";
import { fetchHealth, type HealthResponse } from "@/lib/api";

type Status = "checking" | "online" | "offline";

export function HealthStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((data) => {
        setHealth(data);
        setStatus("online");
        setError("");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setStatus("offline");
        setError(err instanceof Error ? err.message : "Unable to reach API");
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <section className="status-panel" aria-live="polite">
      <div className="status-head">
        <div className="status-label"><Activity size={18} /> Backend connection</div>
        <span className={`status-pill ${status}`}>
          {status === "online" ? <CheckCircle2 size={14} /> : status === "offline" ? <CircleAlert size={14} /> : <RefreshCw size={14} />}
          {status === "online" ? "Connected" : status === "offline" ? "Offline" : "Checking"}
        </span>
      </div>
      <p className="status-description">
        {status === "online"
          ? `FastAPI ${health?.version} is responding. Your full-stack connection works.`
          : status === "checking"
            ? "Connecting to the local FastAPI service..."
            : "Start the backend in a separate PowerShell window, then try again."}
      </p>
      {status === "offline" && <p className="error-detail">{error}</p>}
      <button type="button" className="refresh-button" onClick={() => { setStatus("checking"); setAttempt((x) => x + 1); }}>
        <RefreshCw size={15} /> Check connection
      </button>
    </section>
  );
}
