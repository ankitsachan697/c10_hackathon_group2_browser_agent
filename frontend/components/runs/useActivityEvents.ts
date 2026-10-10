"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ActivityEvent } from "@/lib/types";

export function useActivityEvents(scope: "run" | "operation", id?: string, terminal = false): { events: ActivityEvent[]; error: string } {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState("");
  const cursor = useRef(0);
  const scopeId = useRef("");

  useEffect(() => {
    const identity = `${scope}:${id ?? ""}`;
    if (scopeId.current !== identity) {
      scopeId.current = identity;
      cursor.current = 0;
      Promise.resolve().then(() => { setEvents([]); setError(""); });
    }
    if (!id) return;
    let active = true;
    const poll = async () => {
      try {
        const incoming = await api<ActivityEvent[]>(`/api/${scope === "run" ? "runs" : "operations"}/${id}/events?after_seq=${cursor.current}`);
        if (!active) return;
        const valid = Array.isArray(incoming) ? incoming.filter(item => typeof item.seq === "number" && typeof item.kind === "string") : [];
        if (valid.length) {
          cursor.current = Math.max(cursor.current, ...valid.map(item => item.seq));
          setEvents(current => [...current, ...valid.filter(item => !current.some(existing => existing.seq === item.seq))].sort((a, b) => a.seq - b.seq));
        }
        setError("");
      } catch (failure) {
        if (active) setError(failure instanceof Error ? failure.message : "Activity is temporarily unavailable");
      }
    };
    void poll();
    const timer = window.setInterval(() => { void poll(); }, terminal ? 5000 : 1200);
    return () => { active = false; window.clearInterval(timer); };
  }, [scope, id, terminal]);

  return { events, error };
}
