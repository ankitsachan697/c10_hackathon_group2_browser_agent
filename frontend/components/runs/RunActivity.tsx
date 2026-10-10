"use client";

import type { ActivityEvent } from "@/lib/types";
import { useActivityEvents } from "@/components/runs/useActivityEvents";

function description(event: ActivityEvent): string {
  const payload = event.payload ?? {};
  if (!event.kind) return "Activity received";
  if (event.kind.startsWith("action.")) return `${String(payload.action ?? "browser action")} ${event.kind.split(".")[1]}`;
  if (event.kind === "log") return String(payload.message ?? "Browser output");
  if (event.kind === "generation.completed") return `Discovery completed via ${String(payload.agent_source ?? "configured agent")}${payload.agent_id ? ` · ${String(payload.agent_id)}` : ""}`;
  if (event.kind === "repair.started") return `Repair agent started for ${String(payload.category ?? "failure")}`;
  if (event.kind === "repair.failed") return `Repair agent failed: ${String(payload.error_code ?? "unavailable")}`;
  if (event.kind === "repair.finished") return `Repair completed via ${String(payload.source ?? "configured agent")}`;
  if (event.kind === "visual.finished") return `Visual check: ${String(payload.status ?? "unavailable")}${payload.agent_status ? ` · agent ${String(payload.agent_status)}` : ""}`;
  if (event.kind === "run.attempt_finished") return `Attempt ${String(payload.attempt ?? "")}: ${payload.passed ? "passed" : "failed"}`;
  return event.kind.replaceAll(".", " ");
}

export function RunActivity({ runId, operationId, suppliedEvents, terminal = false }: { runId?: string; operationId?: string; suppliedEvents?: ActivityEvent[]; terminal?: boolean }) {
  const feed = useActivityEvents(runId ? "run" : "operation", suppliedEvents ? undefined : runId ?? operationId, terminal);
  const events = suppliedEvents ?? feed.events;
  const error = suppliedEvents ? "" : feed.error;

  return <section className="activity-panel" aria-label="Live activity">
    <div className="activity-head"><strong>Activity log</strong><span>Updates automatically</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {events.length === 0 ? <p className="activity-empty">Waiting for recorded events…</p> : <ol className="activity-list" aria-live="polite">{events.map(event => <li key={event.seq} className={`activity-${event.source}`}><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString()}</time><span className="activity-source">{event.source}</span><span>{description(event)}</span></li>)}</ol>}
  </section>;
}
