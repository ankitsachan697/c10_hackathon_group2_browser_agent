"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { ExternalLink, Play, RefreshCw, RotateCcw, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Journey, Project, Run } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function ProjectDrawer({ project, initialTab, onClose }: {
  project: Project; initialTab: "journeys" | "history"; onClose: () => void;
}) {
  const [tab, setTab] = useState(initialTab);
  const [data, setData] = useState<{ journeys: Journey[]; runs: Run[] } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [latest, setLatest] = useState<Run | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const tabId = useId();
  const load = useCallback(async (signal?: AbortSignal) => {
    const [journeys, runs] = await Promise.all([
      api<Journey[]>("/api/journeys", { signal }), api<Run[]>("/api/runs", { signal }),
    ]);
    const scoped = journeys.filter(journey => journey.project_id === project.id);
    const ids = new Set(scoped.map(journey => journey.id));
    return { journeys: scoped, runs: runs.filter(run => run.project_id === project.id || (run.journey_id && ids.has(run.journey_id))).sort((a, b) => b.created_at.localeCompare(a.created_at)) };
  }, [project.id]);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Project details unavailable"); });
    return () => controller.abort();
  }, [load]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key !== "Tab") return;
      const elements = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), [tabindex="0"]') ?? []);
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", keydown);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", keydown); previous?.focus(); };
  }, [onClose]);
  const execute = async (key: string, path: string, body?: { mode?: "snapshot"; background?: boolean }) => {
    if (busy) return;
    setBusy(key); setError(""); setLatest(null);
    try {
      const result = await api<Run | Run[]>(path, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) });
      const results = Array.isArray(result) ? result : [result];
      setLatest(results.at(-1) ?? null); setTab("history");
      setData(await load());
      if (!results.length) setError("No active saved journeys to run.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not execute saved script"); }
    finally { setBusy(null); }
  };
  const refresh = async () => {
    setBusy("refresh"); setError("");
    try { setData(await load()); } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not refresh project"); }
    finally { setBusy(null); }
  };
  return createPortal(<div className="project-drawer-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div ref={panel} className="project-drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <header className="project-drawer-header"><div><p className="eyebrow">Project workspace</p><h2 id={titleId}>{project.name}</h2><p>{project.description || "Saved journeys and their execution history."}</p></div><button ref={closeButton} className="icon-button" aria-label="Close project" onClick={onClose}><X size={20}/></button></header>
      <div className="project-drawer-toolbar"><span className="muted">Runs reuse saved Playwright scripts. No new discovery.</span><div className="run-actions"><Button disabled={!data || Boolean(busy) || !data.journeys.some(journey => journey.active && journey.script.trim())} onClick={() => void execute("all", `/api/projects/${project.id}/run`)}><Play size={14}/>Run all journeys</Button><Button className="button-secondary" aria-label="Refresh project" disabled={Boolean(busy)} onClick={() => void refresh()}><RefreshCw size={14}/></Button></div></div>
      <div className="tabs project-tabs" role="tablist" aria-label="Project details">{(["journeys", "history"] as const).map(name => <button key={name} id={`${tabId}-${name}`} role="tab" aria-selected={tab === name} aria-controls={`${tabId}-panel`} onClick={() => setTab(name)}>{name === "journeys" ? "Journeys" : "Run history"}{data && <span className="tab-count">{name === "journeys" ? data.journeys.length : data.runs.length}</span>}</button>)}</div>
      <div className="project-drawer-content" id={`${tabId}-panel`} role="tabpanel" aria-labelledby={`${tabId}-${tab}`}>
        {error && <p role="alert" className="form-error">{error}</p>}
        {busy && busy !== "refresh" && <p role="status" className="muted">Executing saved script… Open Runs to follow live activity.</p>}
        {latest && <div className="project-run-result"><StatusBadge status={latest.status}/><Link className="button" href={`/runs/${latest.id}`}>Open latest run<ExternalLink size={14}/></Link></div>}
        {!data ? !error && <p className="muted">Loading journeys and history…</p> : tab === "journeys" ? <>
          {!data.journeys.length && <p className="evidence-empty">No saved journeys yet. Create a journey to record your first script.</p>}
          {data.journeys.map(journey => <article className="project-journey" key={journey.id}><div><h3>{journey.name}</h3><p>{journey.target_url}</p><span className="muted">{!journey.active ? "Inactive" : journey.script.trim() ? "Saved Playwright script ready" : "No saved script"}</span></div><Button disabled={Boolean(busy) || !journey.active || !journey.script.trim()} onClick={() => void execute(journey.id, `/api/journeys/${journey.id}/run`, { background: true })}><Play size={14}/>Run saved script</Button></article>)}
        </> : <>
          {!data.runs.length && <p className="evidence-empty">No runs yet. Run a saved journey to start its history.</p>}
          {data.runs.map(run => <article className="project-history-row" key={run.id}><div><div className="project-history-title"><Link aria-label={`Open run ${run.id}`} href={`/runs/${run.id}`}>{data.journeys.find(journey => journey.id === run.journey_id)?.name ?? "Saved journey"}<ExternalLink size={13}/></Link><StatusBadge status={run.status}/></div><p><time dateTime={run.created_at}>{new Date(run.created_at).toLocaleString()}</time> · v{run.script_version ?? "—"} · {run.attempt_count} {run.attempt_count === 1 ? "attempt" : "attempts"}</p><span className="muted">{run.id.slice(0, 12)} · {run.trigger_source.replaceAll("_", " ")}</span></div><Button className="button-secondary" title="Execute the exact saved script version from this run" disabled={Boolean(busy) || !data.journeys.some(journey => journey.id === run.journey_id && journey.active)} onClick={() => void execute(run.id, `/api/runs/${run.id}/rerun`, { mode: "snapshot", background: true })}><RotateCcw size={14}/>Rerun this version</Button></article>)}
        </>}
      </div>
      <footer className="project-drawer-footer"><Link href="/runs" className="button button-secondary">View all runs</Link><Button onClick={onClose} className="button-secondary">Close</Button></footer>
    </div>
  </div>, document.body);
}
