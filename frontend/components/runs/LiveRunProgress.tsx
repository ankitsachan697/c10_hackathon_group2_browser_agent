"use client";

import { useState } from "react";
import type { ActivityEvent } from "@/lib/types";

type Props = { operationEvents: ActivityEvent[]; runEvents: ActivityEvent[]; runStatus?: string };

export function LiveRunProgress({ operationEvents, runEvents, runStatus }: Props) {
  const [view, setView] = useState<"steps" | "console">("steps");
  const discovery = operationEvents.findLast(event => event.kind === "generation.completed");
  const planned = Array.isArray(discovery?.payload.discovered_steps) ? discovery.payload.discovered_steps.filter((step): step is string => typeof step === "string") : [];
  const actions = runEvents.filter(event => event.kind.startsWith("action.") && typeof event.payload.action === "string");
  const consoleEvents = [...operationEvents, ...runEvents].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.seq - b.seq);
  const outcome = runStatus === "PASSED" || runStatus === "PASSED_AFTER_REPAIR" ? "First run passed" : runStatus === "NEEDS_ATTENTION" || runStatus === "FAILED" ? "Needs attention" : "Verification in progress";

  return <section className="live-progress" aria-label="Live verification">
    <div className="live-progress-head"><div><p className="eyebrow">Live verification</p><h2>{outcome}</h2><p>Planned discovery is separate from observed browser actions.</p></div><span className="run-state">{runStatus ?? "Waiting for run"}</span></div>
    <div className="live-switch" role="tablist" aria-label="Live run views"><button type="button" role="tab" aria-selected={view === "steps"} onClick={() => setView("steps")}>Step progression</button><button type="button" role="tab" aria-selected={view === "console"} onClick={() => setView("console")}>Live console</button></div>
    {view === "steps" ? <div className="live-step-columns">
      <section><h3>Planned by discovery <span>{planned.length}</span></h3>{planned.length ? <ol className="planned-steps">{planned.map((step, index) => <li key={`${index}-${step}`}><span>Planned</span>{step}</li>)}</ol> : <p className="muted">Waiting for discovery to identify the flow.</p>}</section>
      <section><h3>Observed in browser <span>{actions.length}</span></h3>{actions.length ? <ol className="observed-actions">{actions.map(event => <li key={event.seq} className={`action-${event.kind.split(".")[1]}`}><span>{new Date(event.created_at).toLocaleTimeString()}</span><strong>{`Attempt ${String(event.payload.attempt ?? 1)} · ${String(event.payload.action)} · ${event.kind.split(".")[1]}`}</strong></li>)}</ol> : <p className="muted">No browser actions recorded yet.</p>}</section>
    </div> : <div role="tabpanel" className="live-console"><ol>{consoleEvents.map(event => <li key={`${event.scope_type}-${event.seq}`}><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString()}</time><span>{event.source}</span><code>{event.kind === "log" ? String(event.payload.message ?? "") : event.kind.replaceAll(".", " ")}</code></li>)}</ol>{!consoleEvents.length && <p className="muted">Waiting for activity…</p>}</div>}
  </section>;
}
