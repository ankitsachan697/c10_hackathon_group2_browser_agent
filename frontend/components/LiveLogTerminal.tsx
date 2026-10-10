"use client";

import React, { useState, useEffect, useRef } from "react";
import { Terminal, Shield, Copy, Check, Trash2, Filter } from "lucide-react";

export interface LogEntry {
  timestamp: string;
  level: string;
  agent: string;
  message: string;
}

interface Props {
  logs: LogEntry[];
  onClear?: () => void;
}

export function LiveLogTerminal({ logs, onClear }: Props) {
  const [selectedAgent, setSelectedAgent] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const agentsList = ["ALL", "Flow Discovery Agent", "Script Generator Agent", "Execution Agent", "Error Diagnosis Agent", "Adaptive Repair Agent", "Regression Monitor Agent", "Orchestrator"];

  const filteredLogs = logs.filter((log) => {
    const matchesAgent =
      selectedAgent === "ALL" ||
      log.agent?.toLowerCase().includes(selectedAgent.toLowerCase());
    const matchesSearch =
      !searchQuery ||
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.agent.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesAgent && matchesSearch;
  });

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const handleCopyLogs = () => {
    const text = logs
      .map((l) => `[${l.timestamp}] [${l.level}] [${l.agent}] ${l.message}`)
      .join("\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLevelStyle = (level: string) => {
    switch (level?.toUpperCase()) {
      case "ERROR":
        return "text-red-400 bg-red-950/40 border-red-800/50";
      case "WARN":
        return "text-amber-400 bg-amber-950/40 border-amber-800/50";
      case "SUCCESS":
        return "text-emerald-400 bg-emerald-950/40 border-emerald-800/50";
      default:
        return "text-cyan-400 bg-cyan-950/30 border-cyan-800/40";
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800 gap-2">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span className="font-mono text-xs font-semibold tracking-wider text-slate-200">
            AGENT EXECUTION TELEMETRY
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950/50 border border-emerald-800/50 text-emerald-400">
            <Shield className="w-3 h-3 text-emerald-400" /> ENCRYPTED SECRETS MASKED
          </span>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-2 py-1 text-xs rounded bg-slate-950 border border-slate-800 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 w-32 md:w-48"
          />

          <button
            onClick={handleCopyLogs}
            className="p-1.5 rounded text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 transition"
            title="Copy logs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          {onClear && (
            <button
              onClick={onClear}
              className="p-1.5 rounded text-slate-400 hover:text-red-400 bg-slate-800 hover:bg-slate-700 transition"
              title="Clear terminal"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 px-3 py-1.5 bg-slate-900/60 border-b border-slate-800/60 overflow-x-auto text-[11px] font-mono scrollbar-none">
        <Filter className="w-3 h-3 text-slate-500 mr-1 flex-shrink-0" />
        {agentsList.map((ag) => (
          <button
            key={ag}
            onClick={() => setSelectedAgent(ag)}
            className={`px-2 py-0.5 rounded whitespace-nowrap transition ${
              selectedAgent === ag
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            {ag.replace(" Agent", "")}
          </button>
        ))}
      </div>

      {/* Log Feed */}
      <div className="flex-1 p-3 overflow-y-auto font-mono text-xs space-y-1.5 min-h-[260px] max-h-[380px] bg-slate-950/95 scrollbar-thin scrollbar-thumb-slate-800">
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 text-xs">
            <Terminal className="w-6 h-6 mb-2 text-slate-600 animate-pulse" />
            <span>Awaiting agent execution events...</span>
            <span className="text-[11px] text-slate-600 mt-1">Live logs stream automatically when tasks start.</span>
          </div>
        ) : (
          filteredLogs.map((log, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2.5 py-0.5 leading-relaxed hover:bg-slate-900/40 px-1.5 rounded group"
            >
              <span className="text-slate-500 select-none text-[10px] w-14 shrink-0 font-light">
                {log.timestamp}
              </span>

              <span
                className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold shrink-0 border ${getLevelStyle(
                  log.level
                )}`}
              >
                {log.level || "INFO"}
              </span>

              <span className="text-cyan-400 font-semibold shrink-0 text-[11px]">
                [{log.agent || "System"}]:
              </span>

              <span
                className={`break-all ${
                  log.message.includes("[REDACTED_SECRET")
                    ? "text-emerald-300 font-bold"
                    : log.level === "ERROR"
                    ? "text-red-300"
                    : log.level === "WARN"
                    ? "text-amber-300"
                    : "text-slate-300"
                }`}
              >
                {log.message}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
