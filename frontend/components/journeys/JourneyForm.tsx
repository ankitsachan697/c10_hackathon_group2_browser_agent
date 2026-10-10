"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Eye, EyeOff, FolderPlus, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { GenerationOperation, Project } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CreateProjectDialog } from "@/components/projects/CreateProjectDialog";
import { RunActivity } from "@/components/runs/RunActivity";

const operationKey = "outskill.activeGeneration";

export function JourneyForm() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState("");
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [objective, setObjective] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [mode, setMode] = useState<"headless" | "headed">("headless");
  const [offline, setOffline] = useState(false);
  const [operation, setOperation] = useState<GenerationOperation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submitKey = useRef<string | null>(null);
  const operationId = operation?.id;
  const operationStatus = operation?.status;

  const loadProjects = useCallback(async () => {
    setProjectsLoading(true); setProjectsError("");
    try {
      const values = await api<Project[]>("/api/projects");
      setProjects(values);
      setProjectId(current => current || values[0]?.id || "");
    } catch (failure) {
      setProjectsError(failure instanceof Error ? failure.message : "Projects unavailable");
    } finally { setProjectsLoading(false); }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadProjects);
    const savedId = sessionStorage.getItem(operationKey);
    if (savedId) {
      void api<GenerationOperation>(`/api/operations/${savedId}`).then(setOperation).catch(() => sessionStorage.removeItem(operationKey));
    }
  }, [loadProjects]);

  useEffect(() => {
    if (!operationId || operationStatus === "FAILED" || operationStatus === "COMPLETED") return;
    const poll = () => {
      void api<GenerationOperation>(`/api/operations/${operationId}`).then(setOperation).catch(failure => {
        setError(failure instanceof Error ? failure.message : "Operation status unavailable");
      });
    };
    poll();
    const timer = window.setInterval(poll, 1200);
    return () => window.clearInterval(timer);
  }, [operationId, operationStatus]);

  const createdProject = (project: Project) => {
    setProjects(values => [...values, project]);
    setProjectId(project.id);
    setProjectDialog(false);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || operation || !projectId || !name.trim() || !url.trim() || !objective.trim()) return;
    setBusy(true); setError("");
    const key = submitKey.current ?? crypto.randomUUID();
    submitKey.current = key;
    try {
      const result = await api<GenerationOperation>("/api/operations/generations", {
        method: "POST", headers: { "Idempotency-Key": key },
        body: JSON.stringify({ project_id: projectId, name: name.trim(), target_url: url.trim(), objective: objective.trim(),
          username: username || undefined, password: password || undefined, browser_mode: mode, offline }),
      });
      sessionStorage.setItem(operationKey, result.id);
      setPassword("");
      setOperation(result);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Journey could not be started");
    } finally { setBusy(false); }
  };

  const canSubmit = Boolean(projectId && name.trim() && url.trim() && objective.trim() && Boolean(username) === Boolean(password));
  const startAnother = () => {
    sessionStorage.removeItem(operationKey);
    submitKey.current = null;
    setOperation(null);
    setName(""); setUrl(""); setObjective(""); setUsername(""); setPassword(""); setError("");
  };
  return <div className="page journey-create">
    <div className="page-heading"><div><p className="eyebrow">New journey</p><h1>Describe what the browser should do</h1><p>Discovery creates a saved Playwright script, then runs it once automatically.</p></div></div>
    <Card>
      <form onSubmit={submit} className="journey-form">
        <div className="journey-section-heading"><span>01</span><div><h2>Journey</h2><p>Group it in a project and describe the outcome you expect.</p></div></div>
        <div className="form-grid">
          <div className="project-field">
            {projectsLoading ? <p className="muted">Loading projects…</p> : projectsError ? <div className="inline-error"><span>{projectsError}</span><Button type="button" onClick={loadProjects} className="button-secondary">Retry projects</Button></div> : projects.length === 0 ? <div className="first-project"><FolderPlus/><div><strong>Create a project to begin</strong><span>Projects hold related journeys and run history.</span></div><Button type="button" onClick={() => setProjectDialog(true)}>Create first project</Button></div> : <label>Project<select aria-label="Project" value={projectId} onChange={event => event.target.value === "__new__" ? setProjectDialog(true) : setProjectId(event.target.value)}>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}<option value="__new__">+ New project…</option></select></label>}
          </div>
          <label>Journey name<input aria-label="Journey name" value={name} onChange={event => setName(event.target.value)} placeholder="Login and verify dashboard" required/></label>
          <label className="full">Target URL<input aria-label="Target URL" type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://app.example/login" required/></label>
          <label className="full">Objective<textarea aria-label="Objective" value={objective} onChange={event => setObjective(event.target.value)} rows={3} placeholder="Log in and verify the success message. Keep credentials in the fields below." required/></label>
        </div>
        <div className="journey-section-heading"><span>02</span><div><h2>Credentials</h2><p>Optional. These are passed to the browser worker, not the discovery agent.</p></div></div>
        <div className="form-grid">
          <label>Username<input aria-label="Username" autoComplete="username" value={username} onChange={event => setUsername(event.target.value)}/></label>
          <label>Password<div className="password-field"><input aria-label="Password" autoComplete="current-password" type={showPassword ? "text" : "password"} value={password} onChange={event => setPassword(event.target.value)}/><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={16}/> : <Eye size={16}/>}</button></div></label>
          {Boolean(username) !== Boolean(password) && <p className="full form-error">Supply both username and password, or leave both empty.</p>}
        </div>
        <div className="journey-section-heading"><span>03</span><div><h2>Browser mode</h2><p>Choose how the first run opens Chromium.</p></div></div>
        <div className="browser-mode-options" role="radiogroup" aria-label="Browser mode">
          <label className={mode === "headless" ? "mode-card selected" : "mode-card"}><input type="radio" name="browser_mode" checked={mode === "headless"} onChange={() => setMode("headless")}/><strong>Headless</strong><span>Run in the configured browser worker.</span></label>
          <label className={mode === "headed" ? "mode-card selected" : "mode-card"}><input type="radio" name="browser_mode" checked={mode === "headed"} onChange={() => setMode("headed")}/><strong>Watch in browser</strong><span>Show Chromium where the worker runs. A hosted server needs a paired local browser.</span></label>
        </div>
        <label className="offline-row"><input type="checkbox" checked={offline} onChange={event => setOffline(event.target.checked)}/>Use local offline script generation if n8n is unavailable</label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="wizard-actions"><Button type="submit" aria-label="Generate and run" disabled={!canSubmit || busy || Boolean(operation)}><Sparkles size={16}/>{busy ? "Starting…" : "Generate and run"}</Button></div>
      </form>
    </Card>
    {operation && <Card><div className="operation-heading"><div><p className="eyebrow">Live activity</p><h2>{operation.status === "FAILED" ? "Generation needs attention" : operation.status === "COMPLETED" ? "First run complete" : "Discovering and running"}</h2></div><div className="run-actions">{operation.run_id && <Link className="button primary-link" href={`/runs/${operation.run_id}`}>Open run</Link>}{["FAILED", "COMPLETED"].includes(operation.status) && <Button type="button" className="button-secondary" onClick={startAnother}>Create another journey</Button>}</div></div>
      {operation.error_message && <p className="form-error" role="alert">{operation.error_message}</p>}
      <div className="journey-activity-stack"><RunActivity operationId={operation.id}/>{operation.run_id && <RunActivity runId={operation.run_id}/>}</div>
    </Card>}
    <CreateProjectDialog open={projectDialog} onClose={() => setProjectDialog(false)} onCreated={createdProject}/>
  </div>;
}
