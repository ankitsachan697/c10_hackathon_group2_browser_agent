export type ApiEnvelope<T> = { data: T; error: { code: string; message: string } | null; meta: Record<string, number> };
export type Project = { id: string; name: string; description: string; archived?: number };
export type Journey = { id: string; project_id: string; name: string; target_url: string; script: string; active: number };
export type Run = { id: string; journey_id?: string; status: string; trigger_source: string; attempt_count: number; created_at: string };
export type Schedule = { id: string; journey_id?: string; project_id?: string; local_time: string; timezone: string; enabled: number; next_run?: string };
