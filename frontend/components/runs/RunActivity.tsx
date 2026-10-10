"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ActivityEvent, Run } from "@/lib/types";

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

export function RunActivity({ runId, operationId }: { runId?: string; operationId?: string }) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const cursor = useRef(0);
  const scope = runId ? `/api/runs/${runId}` : `/api/operations/${operationId}`;

  useEffect(() => {
    cursor.current = 0;
    let active = true;
    void Promise.resolve().then(() => { if (active) setEvents([]); });
    const poll = async () => {
      try {
        const incoming = await api<ActivityEvent[]>(`${scope}/events?after_seq=${cursor.current}`);
        if (!active) return;
        const valid = Array.isArray(incoming) ? incoming.filter(item => typeof item.seq === "number" && typeof item.kind === "string") : [];
        if (valid.length) {
          cursor.current = Math.max(cursor.current, ...valid.map(item => item.seq));
          setEvents(current => [...current, ...valid.filter(item => !current.some(existing => existing.seq === item.seq))].sort((a, b) => a.seq - b.seq));
        }
        if (runId) {
          const run = await api<Run>(scope);
          if (active) setStatus(run.status);
        }
        if (active) setError("");
      } catch (failure) {
        if (active) setError(failure instanceof Error ? failure.message : "Activity is temporarily unavailable");
      }
    };
    void poll();
    const timer = window.setInterval(() => { void poll(); }, 1200);
    return () => { active = false; window.clearInterval(timer); };
  }, [scope, runId]);

  return <section className="activity-panel" aria-label="Live activity">
    <div className="activity-head"><strong>Activity log</strong><span>{status || "Updates automatically"}</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {events.length === 0 ? <p className="activity-empty">Waiting for recorded events…</p> : <ol className="activity-list" aria-live="polite">{events.map(event => <li key={event.seq} className={`activity-${event.source}`}><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleTimeString()}</time><span className="activity-source">{event.source}</span><span>{description(event)}</span></li>)}</ol>}
  </section>;
}
