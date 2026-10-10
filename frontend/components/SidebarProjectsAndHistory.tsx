"use client";

import React, { useState, useEffect } from "react";
import {
  FolderKanban,
  History,
  Play,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Video,
  Layers,
  Trash2,
  FileCode,
  Calendar,
  Award,
  Search,
  ChevronRight,
  Folder,
} from "lucide-react";

export interface TestCase {
  id: string;
  project: string;
  name: string;
  target_url: string;
  objective: string;
  script?: string;
  username?: string;
  password_masked?: string;
  schedule?: string;
  created_at?: string;
  last_run_status?: string;
  last_run_time?: string;
  has_baseline?: boolean;
}

export interface RunRecord {
  run_id: string;
  url: string;
  name: string;
  status: string;
  duration: number;
  timestamp: string;
  screenshots: string[];
  video?: string | null;
  visual_status?: string | null;
  attempts?: number;
}

interface Props {
  backendUrl?: string;
  selectedRunId?: string;
  onLoadScript: (script: string, url: string, objective: string) => void;
  onRunSavedCase: (testCase: TestCase) => void;
  onInspectRun: (run: RunRecord) => void;
  isRunning?: boolean;
}

export function SidebarProjectsAndHistory({
  backendUrl = "http://127.0.0.1:8000",
  selectedRunId,
  onLoadScript,
  onRunSavedCase,
  onInspectRun,
  isRunning = false,
}: Props) {
  const [activeTab, setActiveTab] = useState<"projects" | "history">("projects");
  const [cases, setCases] = useState<TestCase[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [casesRes, runsRes] = await Promise.all([
        fetch(`${backendUrl}/api/test-cases`),
        fetch(`${backendUrl}/api/runs`),
      ]);
      if (casesRes.ok) {
        const data = await casesRes.json();
        setCases(data.cases || []);
      }
      if (runsRes.ok) {
        const data = await runsRes.json();
        setRuns(data.runs || []);
      }
    } catch (e) {
      console.error("Failed to fetch sidebar data", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleDeleteCase = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${backendUrl}/api/test-cases/${id}`, { method: "DELETE" });
      setCases((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      console.error("Delete failed", e);
    }
  };

  // Group cases by project folder
  const filteredCases = cases.filter(
    (c) =>
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.project.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.target_url.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const groupedProjects = filteredCases.reduce<Record<string, TestCase[]>>((acc, tc) => {
    const proj = tc.project || "General";
    if (!acc[proj]) acc[proj] = [];
    acc[proj].push(tc);
    return acc;
  }, {});

  const filteredRuns = runs.filter(
    (r) =>
      (r.name && r.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (r.url && r.url.toLowerCase().includes(searchTerm.toLowerCase())) ||
      r.run_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className="w-full lg:w-80 flex-shrink-0 flex flex-col bg-slate-950/90 border border-slate-800/90 rounded-2xl overflow-hidden shadow-2xl h-full lg:min-h-[820px] backdrop-blur-md">
      {/* Top Header & Tabs */}
      <div className="p-3 bg-slate-900/90 border-b border-slate-800/90 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex rounded-xl bg-slate-950 p-1 border border-slate-800 flex-1 mr-2 shadow-inner">
            <button
              onClick={() => setActiveTab("projects")}
              className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                activeTab === "projects"
                  ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FolderKanban className="w-3.5 h-3.5" />
              <span>Projects ({cases.length})</span>
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                activeTab === "history"
                  ? "bg-indigo-500 text-white shadow-md shadow-indigo-500/20"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>History ({runs.length})</span>
            </button>
          </div>

          <button
            onClick={fetchData}
            disabled={isLoading}
            className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            title="Refresh"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-cyan-400" : ""}`} />
          </button>
        </div>

        {/* Filter Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={activeTab === "projects" ? "Search projects & cases..." : "Search run history..."}
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition"
          />
        </div>
      </div>

      {/* Panel Scroll Content */}
      <div className="flex-1 p-3 overflow-y-auto space-y-3.5 custom-scrollbar max-h-[750px]">
        {activeTab === "projects" ? (
          <div>
            {Object.keys(groupedProjects).length === 0 ? (
              <div className="text-center py-12 px-3 text-slate-500 text-xs">
                <FolderKanban className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                <p className="font-semibold text-slate-400">No Projects Found</p>
                <p className="text-[11px] mt-1 text-slate-600">
                  Save test journeys using &quot;Save Suite&quot; to organize scripts into project folders.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {Object.entries(groupedProjects).map(([projName, projCases]) => (
                  <div key={projName} className="space-y-2">
                    <div className="flex items-center gap-1.5 px-1 text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider">
                      <Folder className="w-3.5 h-3.5 text-cyan-400" />
                      <span>{projName}</span>
                      <span className="text-slate-600 font-normal">({projCases.length})</span>
                    </div>

                    <div className="space-y-2">
                      {projCases.map((tc) => (
                        <div
                          key={tc.id}
                          className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/90 transition shadow-sm group"
                        >
                          <div className="flex items-start justify-between gap-1.5 mb-1.5">
                            <h4 className="font-semibold text-xs text-slate-200 group-hover:text-cyan-300 transition line-clamp-1">
                              {tc.name}
                            </h4>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold flex items-center gap-0.5 flex-shrink-0 ${
                                tc.last_run_status === "PASSED"
                                  ? "bg-emerald-950 text-emerald-400 border border-emerald-800/80"
                                  : tc.last_run_status === "FAILED"
                                  ? "bg-red-950 text-red-400 border border-red-800/80"
                                  : "bg-slate-800 text-slate-400"
                              }`}
                            >
                              {tc.last_run_status === "PASSED" ? (
                                <CheckCircle2 className="w-2.5 h-2.5" />
                              ) : (
                                <XCircle className="w-2.5 h-2.5" />
                              )}
                              {tc.last_run_status || "UNTESTED"}
                            </span>
                          </div>

                          <p className="text-[11px] font-mono text-slate-400 truncate mb-1">
                            {tc.target_url}
                          </p>

                          <div className="flex flex-wrap items-center gap-1.5 mb-2.5">
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800 flex items-center gap-1">
                              <Calendar className="w-2.5 h-2.5 text-indigo-400" />
                              {tc.schedule || "Manual"}
                            </span>
                            {tc.has_baseline && (
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950/70 text-indigo-300 border border-indigo-800/60 flex items-center gap-0.5">
                                <Award className="w-2.5 h-2.5 text-indigo-400" /> Baseline
                              </span>
                            )}
                          </div>

                          {/* Quick Actions */}
                          <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[11px]">
                            {tc.script && (
                              <button
                                onClick={() => onLoadScript(tc.script!, tc.target_url, tc.objective)}
                                className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                                title="Load into Playwright Editor"
                              >
                                <FileCode className="w-3 h-3 text-cyan-400" />
                                <span>Load</span>
                              </button>
                            )}

                            <div className="flex items-center gap-1.5 ml-auto">
                              <button
                                onClick={() => onRunSavedCase(tc)}
                                disabled={isRunning}
                                className="flex items-center gap-1 px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition active:scale-95 disabled:opacity-50 shadow-sm"
                                title="Run this test case"
                              >
                                <Play className="w-3 h-3 fill-current" />
                                <span>Run</span>
                              </button>

                              <button
                                onClick={(e) => handleDeleteCase(tc.id, e)}
                                className="p-1 rounded bg-slate-800/60 hover:bg-red-950 text-slate-400 hover:text-red-400 transition"
                                title="Delete test case"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Run History Tab */
          <div>
            {filteredRuns.length === 0 ? (
              <div className="text-center py-12 px-3 text-slate-500 text-xs">
                <History className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                <p className="font-semibold text-slate-400">No Run History Yet</p>
                <p className="text-[11px] mt-1 text-slate-600">
                  Execute test journeys to populate timeline records, screenshots, and videos.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredRuns.map((r) => {
                  const isSelected = selectedRunId === r.run_id;
                  return (
                    <div
                      key={r.run_id}
                      onClick={() => onInspectRun(r)}
                      className={`p-3 rounded-xl border transition cursor-pointer flex flex-col gap-1.5 ${
                        isSelected
                          ? "bg-slate-900 border-cyan-500/80 shadow-md shadow-cyan-500/10"
                          : "bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/90"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <div className="flex items-center gap-2 truncate">
                          <span
                            className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              r.status === "PASSED" ? "bg-emerald-400 animate-pulse" : "bg-red-400"
                            }`}
                          />
                          <span className="font-semibold text-xs text-slate-200 truncate">
                            {r.name || r.run_id}
                          </span>
                        </div>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold flex-shrink-0 ${
                            r.status === "PASSED"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : "bg-red-950 text-red-400 border border-red-800"
                          }`}
                        >
                          {r.status}
                        </span>
                      </div>

                      <p className="text-[11px] font-mono text-slate-400 truncate">{r.url}</p>

                      <div className="flex flex-wrap items-center justify-between pt-1.5 border-t border-slate-800/60 text-[10px] font-mono text-slate-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5 text-slate-500" />
                          {r.duration}s • {r.timestamp.split(" ")[1] || r.timestamp}
                        </span>

                        <div className="flex items-center gap-1.5">
                          {r.video && (
                            <span className="px-1 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/40 flex items-center gap-0.5">
                              <Video className="w-2.5 h-2.5" /> Vid
                            </span>
                          )}
                          {r.screenshots && r.screenshots.length > 0 && (
                            <span className="px-1 py-0.5 rounded bg-slate-950 text-slate-300 border border-slate-800 flex items-center gap-0.5">
                              <Layers className="w-2.5 h-2.5 text-cyan-400" /> {r.screenshots.length}
                            </span>
                          )}
                          <ChevronRight className="w-3 h-3 text-slate-500" />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
