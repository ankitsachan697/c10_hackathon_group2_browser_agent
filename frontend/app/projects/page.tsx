"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronRight, History, Play, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Project, Run } from "@/lib/types";
import { ActionMenu } from "@/components/ui/ActionMenu";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/ToastProvider";
import { ProjectDrawer } from "@/components/projects/ProjectDrawer";

type Impact = { journeys: number; schedules: number; runs: number; artifacts: number };

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [target, setTarget] = useState<Project | null>(null);
  const [impact, setImpact] = useState<Impact | null>(null);
  const [selected, setSelected] = useState<{ project: Project; tab: "journeys" | "history" } | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const toast = useToast();
  useEffect(() => {
    void api<Project[]>("/api/projects").then(setProjects).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, []);
  const visible = useMemo(() => projects.filter(p => p.name.toLowerCase().includes(query.toLowerCase())), [projects, query]);
  const run = async (project: Project) => {
    if (running) return;
    setRunning(project.id); setError("");
    try {
      const results = await api<Run[]>(`/api/projects/${project.id}/run`, { method: "POST" });
      toast(results.length ? `Executed ${results.length} saved scripts` : "No active saved journeys to run");
      setSelected({ project, tab: "history" });
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not run project"); }
    finally { setRunning(null); }
  };
  const askDelete = async (project: Project) => {
    setError(""); setTarget(project); setImpact(null);
    try { setImpact(await api<Impact>(`/api/projects/${project.id}/deletion-impact`)); }
    catch (failure) { setTarget(null); setError(failure instanceof Error ? failure.message : "Could not load deletion details"); }
  };
  const remove = async () => {
    if (!target) return;
    try {
      await api(`/api/projects/${target.id}`, { method: "DELETE" });
      setProjects(v => v.filter(p => p.id !== target.id)); setTarget(null); setImpact(null);
      toast("Project moved to trash");
    } catch (failure) { setTarget(null); setImpact(null); setError(failure instanceof Error ? failure.message : "Could not delete project"); }
  };
  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">Reusable coverage</p><h1>Projects</h1><p>Open a project to view journeys, run history, and saved scripts.</p></div><Link className="button primary-link" href="/journeys/new"><Plus size={16}/>New journey</Link></div>
    <div className="toolbar"><label className="search"><Search size={16}/><input placeholder="Search projects" value={query} onChange={e => setQuery(e.target.value)}/></label></div>
    {error && <p role="alert" className="form-error">{error}</p>}
    {running && <p role="status" className="muted">Executing saved scripts… You can inspect the live run in Runs.</p>}
    {loading ? <div className="skeleton">Loading projects…</div> : visible.length === 0 ? <EmptyState title={query ? "No matching projects" : "No projects yet"} detail={query ? "Try a different project name." : "Create a journey to start your first project."}/> :
      <DataTable headers={["Project", "Description", "Status", "Actions"]}>
        {visible.map(project => <tr key={project.id} className="project-row" onClick={() => setSelected({ project, tab: "journeys" })}>
          <td><button className="project-open" aria-label={`Open project ${project.name}`} onClick={event => { event.stopPropagation(); setSelected({ project, tab: "journeys" }); }}><strong>{project.name}</strong><ChevronRight size={16}/></button><span className="project-row-hint">Journeys & run history</span></td>
          <td>{project.description || "No description"}</td><td><span className="status status-neutral">{running === project.id ? "Running" : "Ready"}</span></td>
          <td><ActionMenu label="Project actions">
            <button role="menuitem" onClick={() => setSelected({ project, tab: "journeys" })}><ChevronRight size={15}/>Open project</button>
            <button role="menuitem" onClick={() => setSelected({ project, tab: "history" })}><History size={15}/>View run history</button>
            <button role="menuitem" disabled={Boolean(running)} onClick={() => void run(project)}><Play size={15}/>Run now</button>
            <button role="menuitem" className="danger-text" onClick={() => void askDelete(project)}><Trash2 size={15}/>Delete</button>
          </ActionMenu></td>
        </tr>)}
      </DataTable>}
    {selected && <ProjectDrawer key={selected.project.id} project={selected.project} initialTab={selected.tab} onClose={() => setSelected(null)}/>}
    <ConfirmDialog open={Boolean(target && impact)} title={`Delete ${target?.name}?`} confirmLabel="Delete project" onClose={() => { setTarget(null); setImpact(null); }} onConfirm={() => void remove()}>
      {impact && <p>{impact.journeys} journeys, {impact.schedules} schedules, {impact.runs} runs, and {impact.artifacts} artifacts will move to recoverable trash.</p>}
    </ConfirmDialog>
  </div>;
}
