"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Button } from "@/components/ui/Button";

export function CreateProjectDialog({ open, onClose, onCreated }: {
  open: boolean; onClose: () => void; onCreated: (project: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLFormElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement;
    nameRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
      if (event.key !== "Tab") return;
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('input, textarea, button:not([disabled])') ?? []);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); previousFocus.current?.focus(); };
  }, [open, onClose]);
  if (!open) return null;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true); setError("");
    try {
      const project = await api<Project>("/api/projects", {
        method: "POST", body: JSON.stringify({ name: name.trim(), description: description.trim() }),
      });
      onCreated(project); setName(""); setDescription("");
    } catch (value) { setError(value instanceof Error ? value.message : "Project creation failed"); }
    finally { setBusy(false); }
  };
  return <div className="dialog-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <form ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="create-project-title" className="dialog" onSubmit={submit}>
      <p className="eyebrow">Organize reusable journeys</p>
      <h2 id="create-project-title">Create project</h2>
      <div className="dialog-form">
        <label>Project name<input ref={nameRef} aria-label="Project name" value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Project description<textarea aria-label="Project description" value={description} onChange={event => setDescription(event.target.value)} rows={3}/></label>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="dialog-actions"><Button type="button" className="button-secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!name.trim() || busy}>{busy ? "Creating…" : "Create project"}</Button></div>
    </form>
  </div>;
}
