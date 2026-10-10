"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ChevronLeft, ChevronRight, Eye, EyeOff, FolderPlus, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CreateProjectDialog } from "@/components/projects/CreateProjectDialog";

export default function JourneyCreatePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState("");
  const [projectDialog, setProjectDialog] = useState(false);
  const [step, setStep] = useState(1);
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [objective, setObjective] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [headed, setHeaded] = useState(false);
  const [result, setResult] = useState<{ script: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const loadProjects = useCallback(async () => {
    setProjectsLoading(true); setProjectsError("");
    try {
      const values = await api<Project[]>("/api/projects");
      setProjects(values);
      setProjectId(current => current || values[0]?.id || "");
    } catch (value) { setProjectsError(value instanceof Error ? value.message : "Projects unavailable"); }
    finally { setProjectsLoading(false); }
  }, []);
  useEffect(() => { void Promise.resolve().then(loadProjects); }, [loadProjects]);

  const projectCreated = (project: Project) => {
    setProjects(values => [...values, project]); setProjectId(project.id); setProjectDialog(false);
  };
  const selectProject = (value: string) => {
    if (value === "__new__") { setProjectDialog(true); return; }
    setProjectId(value);
  };
  const generate = async () => {
    setBusy(true); setSubmitError("");
    try {
      setResult(await api("/api/journeys/generate", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, name, target_url: url, objective, username: username || undefined, password: password || undefined, browser: { headed } }),
      }));
    } catch (value) { setSubmitError(value instanceof Error ? value.message : "Journey generation failed"); }
    finally { setBusy(false); }
  };

  return <div className="page">
    <div className="page-heading"><div><p className="eyebrow">New journey · Step {step} of 3</p><h1>{step === 1 ? "Describe the journey" : step === 2 ? "Browser and credentials" : "Review and generate"}</h1><p>Generation runs only after your explicit confirmation.</p></div></div>
    <div className="wizard"><aside><span className={step >= 1 ? "done" : ""}>1 · Journey</span><span className={step >= 2 ? "done" : ""}>2 · Browser</span><span className={step >= 3 ? "done" : ""}>3 · Review</span></aside>
      <Card>
        {step === 1 && <div className="form-grid">
          <div className="project-field">
            {projectsLoading ? <span className="muted">Loading projects…</span> : projectsError ? <div className="inline-error"><span>{projectsError}</span><Button onClick={loadProjects} className="button-secondary">Retry projects</Button></div> : projects.length === 0 ? <div className="first-project"><FolderPlus/><div><strong>Create a project to begin</strong><span>Projects group related journeys, schedules, and run history.</span></div><Button onClick={() => setProjectDialog(true)}>Create first project</Button></div> : <label>Project<select aria-label="Project" value={projectId} onChange={event => selectProject(event.target.value)}>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}<option value="__new__">+ New project…</option></select></label>}
          </div>
          <label>Journey name<input aria-label="Journey name" value={name} onChange={event => setName(event.target.value)}/></label>
          <label>Target URL<input aria-label="Target URL" type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://app.example"/></label>
          <label className="full">Objective<textarea aria-label="Objective" value={objective} onChange={event => setObjective(event.target.value)} rows={5} placeholder="Describe actions and the expected outcome. Keep credentials in the secure fields on the next step."/></label>
        </div>}
        {step === 2 && <div className="form-grid">
          <label>Engine<select><option>Playwright · Chromium</option></select></label><label>Viewport<select><option>Desktop · 1440 × 900</option></select></label>
          <label>Username<input aria-label="Username" autoComplete="username" value={username} onChange={event => setUsername(event.target.value)}/></label>
          <label>Password<div className="password-field"><input aria-label="Password" autoComplete="current-password" type={showPassword ? "text" : "password"} value={password} onChange={event => setPassword(event.target.value)}/><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={16}/> : <Eye size={16}/>}</button></div></label>
          <label className="check-row full"><input type="checkbox" checked={headed} onChange={event => setHeaded(event.target.checked)}/>Show browser while running</label>
          <p className="full muted">Credentials are encrypted at rest and injected only into the isolated browser worker. They are never written into the Playwright script or sent to n8n.</p>
        </div>}
        {step === 3 && !result && <div className="review-grid"><div><span>Project</span><strong>{projects.find(project => project.id === projectId)?.name}</strong></div><div><span>Name</span><strong>{name}</strong></div><div><span>Target</span><strong>{url}</strong></div><div><span>Credentials</span><strong>{username ? `${username} · ${password ? "••••••••" : "No password"}` : "Not provided"}</strong></div><div className="full"><span>Objective</span><strong>{objective}</strong></div></div>}
        {result && <div className="success-panel"><Check/><h2>Script ready</h2><p>The generated Playwright script is saved as version 1. Future Run now actions execute this saved version directly.</p><pre>{result.script}</pre></div>}
        {submitError && <p className="form-error" role="alert">{submitError}</p>}
        <div className="wizard-actions">{step > 1 && !result && <Button className="button-secondary" onClick={() => setStep(value => value - 1)}><ChevronLeft size={16}/>Back</Button>}{step < 3 && <Button aria-label="Review journey" onClick={() => setStep(value => value + 1)} disabled={step === 1 && (!projectId || !name || !url)}>{step === 2 ? "Review journey" : "Continue"}<ChevronRight size={16}/></Button>}{step === 3 && !result && <Button aria-label="Generate and save" onClick={generate} disabled={busy || Boolean(username) !== Boolean(password)}><Sparkles size={16}/>{busy ? "Generating…" : "Generate and save"}</Button>}</div>
      </Card>
    </div>
    <CreateProjectDialog open={projectDialog} onClose={() => setProjectDialog(false)} onCreated={projectCreated}/>
  </div>;
}
