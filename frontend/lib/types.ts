export type ApiEnvelope<T> = { data: T; error: { code: string; message: string } | null; meta: Record<string, number> };
export type Project = { id: string; name: string; description: string; archived?: number };
export type Journey = { id: string; project_id: string; name: string; target_url: string; script: string; active: number; has_credentials?: boolean };
export type RunAttempt = { attempt_number: number; status: string; stdout?: string; stderr?: string };
export type Artifact = { id: string; kind: string; storage_path: string; media_type?: string };
export type Run = { id: string; journey_id?: string; status: string; trigger_source: string; attempt_count: number; created_at: string; script_snapshot?: string; repair_patch?: string; diagnosis_json?: string; attempts?: RunAttempt[]; artifacts?: Artifact[] };
export type Schedule = { id: string; journey_id?: string; project_id?: string; local_time: string; timezone: string; enabled: number; next_run?: string };
