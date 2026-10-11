"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Eye, EyeOff, FolderPlus, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { GenerationOperation, Project, Run } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CreateProjectDialog } from "@/components/projects/CreateProjectDialog";
import { LiveRunProgress } from "@/components/runs/LiveRunProgress";
import { useActivityEvents } from "@/components/runs/useActivityEvents";
import { CompanionPicker } from "@/components/browser/CompanionPicker";

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
  const passwordRef = useRef<HTMLInputElement>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [mode, setMode] = useState<"headless" | "headed">("headless");
  const [companionId, setCompanionId] = useState("");
  const [offline, setOffline] = useState(false);
  const [operation, setOperation] = useState<GenerationOperation | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submitKey = useRef<string | null>(null);
  const operationId = operation?.id;
  const operationStatus = operation?.status;
  const operationActive = Boolean(operation && !["FAILED", "COMPLETED"].includes(operation.status));
  const runId = operation?.run_id ?? undefined;
  const runTerminal = ["PASSED", "PASSED_AFTER_REPAIR", "NEEDS_ATTENTION", "FAILED"].includes(run?.status ?? "");
  const operationFeed = useActivityEvents("operation", operationId, operationStatus === "FAILED" || operationStatus === "COMPLETED");
  const runFeed = useActivityEvents("run", runId, runTerminal);

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
    void Promise.resolve().then(() => {
      const query = new URLSearchParams(window.location.search);
      if (query.has("target_url")) setUrl(current => current || query.get("target_url") || "");
      if (query.has("objective")) setObjective(current => current || query.get("objective") || "");
      if (query.has("name")) setName(current => current || query.get("name") || "");
      if (query.has("username")) setUsername(current => current || query.get("username") || "");
    });
    const savedId = sessionStorage.getItem(operationKey);
    if (savedId) {
      void api<GenerationOperation>(`/api/operations/${savedId}`).then(value => {
        if (["FAILED", "COMPLETED"].includes(value.status)) {
          sessionStorage.removeItem(operationKey);
        } else {
          setOperation(value);
        }
      }).catch(() => sessionStorage.removeItem(operationKey));
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

  useEffect(() => {
    if (!runId) return;
    let active = true;
    const poll = () => { void api<Run>(`/api/runs/${runId}`).then(value => { if (active) setRun(value); }).catch(failure => {
      if (active) setError(failure instanceof Error ? failure.message : "Run status unavailable");
    }); };
    poll();
    const timer = window.setInterval(poll, runTerminal ? 5000 : 1200);
    return () => { active = false; window.clearInterval(timer); };
  }, [runId, runTerminal]);

  const createdProject = (project: Project) => {
    setProjects(values => [...values, project]);
    setProjectId(project.id);
    setProjectDialog(false);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || operationActive || !projectId || !name.trim() || !url.trim() || !objective.trim()) return;
    const enteredPassword = passwordRef.current?.value ?? "";
    if (Boolean(username) !== Boolean(enteredPassword)) {
      setError("Supply both username and password, or leave both empty.");
      return;
    }
    setBusy(true); setError("");
    const key = submitKey.current ?? crypto.randomUUID();
    submitKey.current = key;
    try {
      const result = await api<GenerationOperation>("/api/operations/generations", {
        method: "POST", headers: { "Idempotency-Key": key },
        body: JSON.stringify({ project_id: projectId, name: name.trim(), target_url: url.trim(), objective: objective.trim(),
          username: username || undefined, password: enteredPassword || undefined, browser_mode: mode,
          companion_id: mode === "headed" ? companionId || undefined : undefined, offline }),
      });
      sessionStorage.setItem(operationKey, result.id);
      if (passwordRef.current) passwordRef.current.value = "";
      submitKey.current = null;
      setRun(null);
      setOperation(result);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Journey could not be started");
    } finally { setBusy(false); }
  };

  const canSubmit = Boolean(projectId && name.trim() && url.trim() && objective.trim());
  const startAnother = () => {
    sessionStorage.removeItem(operationKey);
    submitKey.current = null;
    setOperation(null);
    setRun(null);
    if (passwordRef.current) passwordRef.current.value = "";
    setName(""); setUrl(""); setObjective(""); setUsername(""); setError("");
  };
  return <div className="page journey-create">
    <div className="page-heading"><div><p className="eyebrow">New journey</p><h1>Describe what the browser should do</h1><p>Discovery creates a saved Playwright script, then runs it once automatically.</p></div></div>
    <Card>
      <form onSubmit={submit} className="journey-form">
        <div className="journey-section-heading"><span>01</span><div><h2>What should the browser verify?</h2><p>Describe the user journey and the outcome to check. The first run starts after you confirm below.</p></div></div>
        <label className="objective-editor">Objective<textarea aria-label="Objective" value={objective} onChange={event => setObjective(event.target.value)} rows={6} placeholder="Log in to the target site and verify the success message. Keep credentials in the secure fields below." required/></label>
        <div className="journey-section-heading"><span>02</span><div><h2>Journey details</h2><p>Group this verification with related runs and set its starting page.</p></div></div>
        <div className="form-grid">
          <div className="project-field">
            {projectsLoading ? <p className="muted">Loading projects…</p> : projectsError ? <div className="inline-error"><span>{projectsError}</span><Button type="button" onClick={loadProjects} className="button-secondary">Retry projects</Button></div> : projects.length === 0 ? <div className="first-project"><FolderPlus/><div><strong>Create a project to begin</strong><span>Projects hold related journeys and run history.</span></div><Button type="button" onClick={() => setProjectDialog(true)}>Create first project</Button></div> : <label>Project<select aria-label="Project" value={projectId} onChange={event => event.target.value === "__new__" ? setProjectDialog(true) : setProjectId(event.target.value)}>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}<option value="__new__">+ New project…</option></select></label>}
          </div>
          <label>Journey name<input aria-label="Journey name" value={name} onChange={event => setName(event.target.value)} placeholder="Login and verify dashboard" required/></label>
          <label className="full">Target URL<input aria-label="Target URL" type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://app.example/login" required/></label>
        </div>
        <div className="journey-section-heading"><span>03</span><div><h2>Credentials</h2><p>Optional. These are passed to the browser worker, not the discovery agent.</p></div></div>
        <div className="form-grid">
          <label>Username<input aria-label="Username" autoComplete="username" value={username} onChange={event => setUsername(event.target.value)}/></label>
          <label>Password<div className="password-field"><input ref={passwordRef} aria-label="Password" autoComplete="current-password" type={showPassword ? "text" : "password"}/><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={16}/> : <Eye size={16}/>}</button></div></label>
        </div>
        <div className="journey-section-heading"><span>04</span><div><h2>Browser mode</h2><p>Choose how the first run opens Chromium.</p></div></div>
        <CompanionPicker mode={mode} onModeChange={setMode} companionId={companionId} onCompanionChange={setCompanionId}/>
        <label className="offline-row"><input type="checkbox" checked={offline} onChange={event => setOffline(event.target.checked)}/>Use local offline script generation if n8n is unavailable</label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="wizard-actions">{operationActive ? <a className="muted" href="#live-verification">A verification is running. View its progress below.</a> : !canSubmit ? <span className="muted">Choose a project and enter the objective, journey name, and target URL.</span> : null}<Button type="submit" aria-label="Verify & record live" disabled={!canSubmit || busy || operationActive}><Sparkles size={16}/>{busy ? "Starting…" : "Verify & record live"}</Button></div>
      </form>
    </Card>
    {operation && <div id="live-verification" className="verification-session"><Card><div className="operation-heading"><p className="eyebrow">Live activity</p><div className="run-actions">{operation.run_id && <Link className="button primary-link" href={`/runs/${operation.run_id}`}>Open run</Link>}{["FAILED", "COMPLETED"].includes(operation.status) && <Button type="button" className="button-secondary" onClick={startAnother}>Create another journey</Button>}</div></div>
      {operation.error_message && <p className="form-error" role="alert">{operation.error_message}</p>}
      <LiveRunProgress operationEvents={operationFeed.events} runEvents={runFeed.events} run={run ?? undefined} runStatus={operation.status === "FAILED" ? "FAILED" : undefined}/>
      {operationFeed.error && <p className="form-error" role="alert">{operationFeed.error}</p>}
      {runFeed.error && <p className="form-error" role="alert">{runFeed.error}</p>}
    </Card></div>}
    <CreateProjectDialog open={projectDialog} onClose={() => setProjectDialog(false)} onCreated={createdProject}/>
  </div>;
}
