"use client";

import React from "react";
import { Sparkles, Terminal, AlertTriangle, ShieldCheck, Eye, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";

export type AgentState = "idle" | "running" | "completed" | "healed" | "failed";

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  state: AgentState;
  model: string;
  lastAction?: string;
}

interface Props {
  agents: Record<string, AgentInfo>;
}

export function AgentStatusCards({ agents }: Props) {
  const getIcon = (id: string) => {
    switch (id) {
      case "discovery_gen":
        return <Sparkles className="w-5 h-5 text-cyan-400" />;
      case "execution":
        return <Terminal className="w-5 h-5 text-emerald-400" />;
      case "diagnosis":
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case "repair":
        return <ShieldCheck className="w-5 h-5 text-violet-400" />;
      case "visual_regression":
        return <Eye className="w-5 h-5 text-pink-400" />;
      default:
        return <Sparkles className="w-5 h-5 text-cyan-400" />;
    }
  };

  const getStateBadge = (state: AgentState) => {
    switch (state) {
      case "running":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 animate-pulse">
            <Loader2 className="w-3 h-3 animate-spin" /> RUNNING
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" /> READY
          </span>
        );
      case "healed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-violet-500/10 text-violet-400 border border-violet-500/30">
            <ShieldCheck className="w-3 h-3" /> HEALED
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30">
            <XCircle className="w-3 h-3" /> FAILED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            <Clock className="w-3 h-3" /> STANDBY
          </span>
        );
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
      {Object.values(agents).map((agent) => {
        const isRunning = agent.state === "running";
        return (
          <div
            key={agent.id}
            className={`relative p-3.5 rounded-xl border transition-all duration-300 ${
              isRunning
                ? "bg-slate-900/90 border-cyan-500/50 shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-500/30"
                : agent.state === "healed"
                ? "bg-slate-900/70 border-violet-500/40"
                : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/50">
                {getIcon(agent.id)}
              </div>
              {getStateBadge(agent.state)}
            </div>

            <h3 className="font-semibold text-sm text-slate-100 truncate">{agent.name}</h3>
            <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{agent.role}</p>

            <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700/50 text-slate-300">
                {agent.model}
              </span>
              <span className="text-right truncate max-w-[100px] text-slate-400">
                {agent.lastAction || "Awaiting task"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
