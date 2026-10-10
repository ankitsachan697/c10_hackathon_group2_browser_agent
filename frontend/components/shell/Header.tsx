"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { Plus, Server, Timer, Workflow } from "lucide-react";
import { backendUrl } from "@/lib/api";

type Health = { status: string; runner_ready: boolean; scheduler_ready: boolean; n8n_connected: boolean };

export function Header() {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    fetch(`${backendUrl}/api/health`).then(response => response.ok ? response.json() : Promise.reject()).then(setHealth).catch(() => setHealth(null));
  }, []);
  const service = (label: string, ready: boolean | undefined, icon: ReactNode) => <span
    className={ready ? "healthy" : "offline"}
    title={`${label} ${ready ? "available" : "unavailable"}`}
  >{icon}{label}</span>;
  return <header className="topbar">
    <div className="health">
      {service("API", health?.status === "healthy", <Server size={14}/>)}
      {service("Runner", health?.runner_ready, <Timer size={14}/>)}
      {service("Scheduler", health?.scheduler_ready, <Workflow size={14}/>)}
      {service("n8n", health?.n8n_connected, <Workflow size={14}/>)}
    </div>
    <Link href="/journeys/new" className="button primary-link"><Plus size={16}/>New journey</Link>
  </header>;
}
