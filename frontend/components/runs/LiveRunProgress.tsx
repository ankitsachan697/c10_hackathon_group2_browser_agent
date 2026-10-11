"use client";

import { useId, useState } from "react";
import { LoaderCircle } from "lucide-react";
import type { ActivityEvent, Run } from "@/lib/types";
import { RunMedia } from "@/components/runs/RunMedia";
import { RunScript } from "@/components/runs/RunScript";
import { RunVisual } from "@/components/runs/RunVisual";
import { activeExecutionStates } from "@/components/ui/ExecutionButton";

type Props = { operationEvents: ActivityEvent[]; runEvents: ActivityEvent[]; runStatus?: string; run?: Run };
const views = [
  { key: "steps", label: "Step progression" },
  { key: "console", label: "Live console" },
  { key: "script", label: "Playwright Script" },
  { key: "screenshots", label: "Screenshots" },
  { key: "recording", label: "Recording" },
  { key: "visual", label: "Visual" },
] as const;
type View = typeof views[number]["key"];

export function LiveRunProgress({ operationEvents, runEvents, runStatus, run }: Props) {
  const [view, setView] = useState<View>("steps");
  const tabId = useId();
  const status = run?.status ?? runStatus;
  const discovery = operationEvents.findLast(event => event.kind === "generation.completed");
  const planned = Array.isArray(discovery?.payload.discovered_steps) ? discovery.payload.discovered_steps.filter((step): step is string => typeof step === "string") : [];
  const actions = runEvents.filter(event => event.kind.startsWith("action.") && typeof event.payload.action === "string");
  const consoleEvents = [...operationEvents, ...runEvents].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.seq - b.seq);
  const outcome = status === "PASSED" || status === "PASSED_AFTER_REPAIR" ? "First run passed" : status === "NEEDS_ATTENTION" || status === "FAILED" ? "Needs attention" : "Verification in progress";
  const selectedView = !run && view !== "steps" && view !== "console" ? "steps" : view;
  const active = activeExecutionStates.includes(status ?? "");
  const waiting = active && actions.length === 0;
  const waitingLabel = status === "STARTING" ? "Starting verification…"
    : run ? "Preparing remote Chromium and starting the recording…"
    : discovery ? "Discovery finished. Preparing the first browser run…"
    : status === "QUEUED" ? "Verification queued. Waiting for discovery to start…"
    : "Discovery is inspecting the target and identifying the flow…";

  return <section className="live-progress" aria-label="Live verification">
    <div className="live-progress-head"><div><p className="eyebrow">Live verification</p><h2>{outcome}</h2><p>Follow the browser actions and inspect the saved evidence.</p></div><span className="run-state">{active && <span className="execution-dot" aria-hidden="true"/>}{status?.replaceAll("_", " ") ?? "Waiting for run"}</span></div>
    {waiting && <div className="activity-loading" role="status" aria-label="Browser activity"><LoaderCircle size={20} aria-hidden="true" className="execution-spinner"/><div><strong>{waitingLabel}</strong><p>Live actions will appear here automatically. The recording becomes available after the browser closes.</p></div></div>}
    <div className="live-switch" role="tablist" aria-label="Verification views">{views.map(({ key, label }, index) => <button
      key={key} id={`${tabId}-${key}`} type="button" role="tab"
      aria-selected={selectedView === key} aria-controls={`${tabId}-panel`}
      tabIndex={selectedView === key ? 0 : -1}
      disabled={!run && index > 1} onClick={() => setView(key)}
      onKeyDown={event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const available = run ? views.length : 2;
        const next = event.key === "Home" ? 0 : event.key === "End" ? available - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + available) % available;
        setView(views[next].key);
        document.getElementById(`${tabId}-${views[next].key}`)?.focus();
      }}
    >{label}</button>)}</div>
    <div role="tabpanel" id={`${tabId}-panel`} aria-labelledby={`${tabId}-${selectedView}`} className="verification-panel">
    {selectedView === "steps" && <div className="live-step-columns">
      <section><h3>Planned by discovery <span>{planned.length}</span></h3>{planned.length ? <ol className="planned-steps">{planned.map((step, index) => <li key={`${index}-${step}`}><span>Planned</span>{step}</li>)}</ol> : <p className="muted">Waiting for discovery to identify the flow.</p>}</section>
      <section><h3>Observed in browser <span>{actions.length}</span></h3>{actions.length ? <ol className="observed-actions">{actions.map(event => <li key={event.seq} className={`action-${event.kind.split(".")[1]}`}><span>{new Date(event.created_at).toLocaleTimeString()}</span><strong>{`Attempt ${String(event.payload.attempt ?? 1)} · ${String(event.payload.action)} · ${event.kind.split(".")[1]}`}</strong></li>)}</ol> : <p className="muted">No browser actions recorded yet.</p>}</section>
    </div>}
    {selectedView === "console" && <div className="live-console"><ol>{consoleEvents.map(event => <li key={`${event.scope_type}-${event.seq}`}><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString()}</time><span>{event.source}</span><code>{event.kind === "log" ? String(event.payload.message ?? "") : event.kind.startsWith("action.") ? `Attempt ${String(event.payload.attempt ?? 1)} · ${String(event.payload.action ?? "browser action")} · ${event.kind.split(".")[1]}` : event.kind.replaceAll(".", " ")}</code></li>)}</ol>{!consoleEvents.length && <p className="muted">Waiting for activity…</p>}</div>}
    {selectedView === "script" && run && (run.script_snapshot ? <RunScript original={run.script_snapshot} healed={run.repair_patch}/> : <p className="evidence-empty">Script is not available yet.</p>)}
    {selectedView === "screenshots" && run && <RunMedia artifacts={run.artifacts ?? []} kind="screenshot"/>}
    {selectedView === "recording" && run && <RunMedia artifacts={run.artifacts ?? []} kind="video"/>}
    {selectedView === "visual" && run && <RunVisual run={run}/>}
    </div>
  </section>;
}
