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
  Plus,
  FileCode,
  Calendar,
  Award,
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
  onLoadScript: (script: string, url: string, objective: string) => void;
  onRunSavedCase: (testCase: TestCase) => void;
  onInspectRun: (run: RunRecord) => void;
  isRunning?: boolean;
}

export function TestSuiteDrawer({
  backendUrl = "http://127.0.0.1:8000",
  onLoadScript,
  onRunSavedCase,
  onInspectRun,
  isRunning = false,
}: Props) {
  const [activeTab, setActiveTab] = useState<"suites" | "history">("suites");
  const [cases, setCases] = useState<TestCase[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch test cases and history
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
      console.error("Failed to fetch test cases or history", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const handleDeleteCase = async (id: string) => {
    try {
      await fetch(`${backendUrl}/api/test-cases/${id}`, { method: "DELETE" });
      setCases((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      console.error("Delete failed", e);
    }
  };

  // Group cases by project folder
  const groupedProjects = cases.reduce<Record<string, TestCase[]>>((acc, tc) => {
    const proj = tc.project || "General";
    if (!acc[proj]) acc[proj] = [];
    acc[proj].push(tc);
    return acc;
  }, {});

  return (
    <div className="flex flex-col bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Tab Header Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-slate-950 p-0.5 border border-slate-800">
            <button
              onClick={() => setActiveTab("suites")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition ${
                activeTab === "suites"
                  ? "bg-slate-800 text-cyan-300 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FolderKanban className="w-3.5 h-3.5 text-cyan-400" />
              Test Suites & Projects ({cases.length})
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition ${
                activeTab === "history"
                  ? "bg-slate-800 text-indigo-300 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <History className="w-3.5 h-3.5 text-indigo-400" />
              Run History & Archives ({runs.length})
            </button>
          </div>
        </div>

        <button
          onClick={fetchData}
          disabled={isLoading}
          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
          title="Refresh suites and run history"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-cyan-400" : ""}`} />
        </button>
      </div>

      {/* Content Area */}
      <div className="p-4 overflow-auto max-h-[380px]">
        {activeTab === "suites" ? (
          <div className="space-y-4">
            {Object.keys(groupedProjects).length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                <FolderKanban className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                No saved test cases yet. Click &quot;Save Suite&quot; in the script viewer to organize test journeys!
              </div>
            ) : (
              Object.entries(groupedProjects).map(([projectName, projectCases]) => (
                <div key={projectName} className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                    <span className="w-2 h-2 rounded-full bg-cyan-400" />
                    PROJECT FOLDER: {projectName} ({projectCases.length})
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {projectCases.map((tc) => (
                      <div
                        key={tc.id}
                        className="p-3 rounded-xl bg-slate-900/80 border border-slate-800/90 hover:border-slate-700 flex flex-col justify-between gap-2.5 transition"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2">
                            <h4 className="font-semibold text-xs text-slate-200 truncate">{tc.name}</h4>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold flex items-center gap-1 ${
                                tc.last_run_status === "PASSED"
                                  ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800"
                                  : tc.last_run_status === "FAILED"
                                  ? "bg-red-950/80 text-red-400 border border-red-800"
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

                          <p className="text-[11px] text-slate-400 font-mono truncate mt-0.5">{tc.target_url}</p>
                          <p className="text-xs text-slate-300 line-clamp-2 mt-1">{tc.objective}</p>
                        </div>

                        {/* Metadata Tags & Actions */}
                        <div className="flex items-center justify-between pt-2 border-t border-slate-800/70 text-[11px] text-slate-400">
                          <div className="flex items-center gap-2">
                            <span className="flex items-center gap-1 text-[10px] font-mono bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                              <Calendar className="w-2.5 h-2.5 text-indigo-400" />
                              {tc.schedule || "Manual"}
                            </span>
                            {tc.has_baseline && (
                              <span className="flex items-center gap-1 text-[10px] font-mono bg-indigo-950/70 text-indigo-300 px-1.5 py-0.5 rounded border border-indigo-800/60">
                                <Award className="w-2.5 h-2.5" /> Baseline
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-1.5">
                            {tc.script && (
                              <button
                                onClick={() => onLoadScript(tc.script!, tc.target_url, tc.objective)}
                                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                                title="Load script into editor"
                              >
                                <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                              </button>
                            )}

                            <button
                              onClick={() => onRunSavedCase(tc)}
                              disabled={isRunning}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-600/90 hover:bg-emerald-500 text-white font-bold text-[11px] transition shadow-sm active:scale-95 disabled:opacity-50"
                              title="Run this test case now"
                            >
                              <Play className="w-3 h-3 fill-current" /> Run
                            </button>

                            <button
                              onClick={() => handleDeleteCase(tc.id)}
                              className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-red-950 text-slate-400 hover:text-red-400 transition"
                              title="Delete test case"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          /* Run History Timeline */
          <div className="space-y-2">
            {runs.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                <History className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                No execution runs recorded yet.
              </div>
            ) : (
              <div className="divide-y divide-slate-800/80">
                {runs.map((r, idx) => (
                  <div
                    key={idx}
                    onClick={() => onInspectRun(r)}
                    className="py-2.5 px-3 rounded-lg hover:bg-slate-900/80 transition cursor-pointer flex flex-wrap items-center justify-between gap-2"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          r.status === "PASSED" ? "bg-emerald-400" : "bg-red-400"
                        }`}
                      />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs text-slate-200">{r.name || r.run_id}</span>
                          <span className="text-[10px] font-mono text-slate-500">[{r.run_id}]</span>
                        </div>
                        <p className="text-[11px] font-mono text-slate-400">{r.url}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-slate-400 flex items-center gap-1 font-mono text-[11px]">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {r.duration}s
                      </span>

                      {r.video && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 font-mono text-[10px] border border-cyan-800/40">
                          <Video className="w-3 h-3" /> Video
                        </span>
                      )}

                      {r.screenshots && r.screenshots.length > 0 && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900 text-slate-300 font-mono text-[10px] border border-slate-800">
                          <Layers className="w-3 h-3 text-cyan-400" /> {r.screenshots.length} shots
                        </span>
                      )}

                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                          r.status === "PASSED"
                            ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                            : "bg-red-950 text-red-400 border border-red-800"
                        }`}
                      >
                        {r.status}
                      </span>

                      <span className="text-[10px] font-mono text-slate-500">{r.timestamp}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
