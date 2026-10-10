"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  Sparkles,
  Copy,
  Check,
  FileCode2,
  Play,
  RotateCcw,
  BookmarkPlus,
  Edit3,
  Eye,
} from "lucide-react";

interface Props {
  originalScript: string;
  healedScript?: string;
  diagnosis?: {
    root_cause?: string;
    failure_category?: string;
    recommended_fix?: string;
    diff_summary?: string;
  };
  isValidating?: boolean;
  onRunScript?: (scriptToRun: string) => void;
  onSaveToSuite?: (scriptToSave: string) => void;
}

export function ScriptDiffViewer({
  originalScript,
  healedScript,
  diagnosis,
  isValidating = false,
  onRunScript,
  onSaveToSuite,
}: Props) {
  const [activeTab, setActiveTab] = useState<"current" | "healed" | "diagnosis">(
    healedScript ? "healed" : "current"
  );
  const [isEditable, setIsEditable] = useState(false);
  const [editableCode, setEditableCode] = useState("");
  const [copied, setCopied] = useState(false);

  // Sync active code to editable textarea
  useEffect(() => {
    const code = activeTab === "healed" && healedScript ? healedScript : originalScript;
    // Sync the editor buffer when the selected script source changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEditableCode(code || "");
  }, [originalScript, healedScript, activeTab]);

  const displayCode = isEditable
    ? editableCode
    : activeTab === "healed" && healedScript
    ? healedScript
    : originalScript;

  const handleCopy = () => {
    navigator.clipboard.writeText(displayCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRun = () => {
    if (onRunScript) {
      onRunScript(isEditable ? editableCode : displayCode);
    }
  };

  const handleSave = () => {
    if (onSaveToSuite) {
      onSaveToSuite(isEditable ? editableCode : displayCode);
    }
  };

  return (
    <div className="flex flex-col bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-xl h-full">
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-slate-900 border-b border-slate-800 gap-2">
        <div className="flex items-center gap-2">
          <FileCode2 className="w-4 h-4 text-cyan-400" />
          <div className="flex rounded-lg bg-slate-950 p-0.5 border border-slate-800">
            <button
              onClick={() => setActiveTab("current")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                activeTab === "current"
                  ? "bg-slate-800 text-slate-100 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Playwright Script
            </button>

            {healedScript && (
              <button
                onClick={() => setActiveTab("healed")}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition ${
                  activeTab === "healed"
                    ? "bg-violet-950/80 text-violet-300 border border-violet-700/60 shadow"
                    : "text-violet-400 hover:text-violet-200"
                }`}
              >
                <Sparkles className="w-3 h-3 text-violet-400" />
                Healed Script
              </button>
            )}

            {diagnosis && (
              <button
                onClick={() => setActiveTab("diagnosis")}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition ${
                  activeTab === "diagnosis"
                    ? "bg-amber-950/80 text-amber-300 border border-amber-700/60 shadow"
                    : "text-amber-400 hover:text-amber-200"
                }`}
              >
                <ShieldAlert className="w-3 h-3 text-amber-400" />
                Diagnosis Report
              </button>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5">
          {activeTab !== "diagnosis" && (
            <button
              onClick={() => setIsEditable(!isEditable)}
              className={`flex items-center gap-1 px-2 py-1 text-xs rounded border transition ${
                isEditable
                  ? "bg-cyan-950/80 border-cyan-500 text-cyan-300 shadow-sm"
                  : "bg-slate-800/80 border-slate-700/60 text-slate-300 hover:text-white"
              }`}
              title={isEditable ? "Switch to read-only view" : "Edit script directly"}
            >
              {isEditable ? <Eye className="w-3 h-3 text-cyan-400" /> : <Edit3 className="w-3 h-3 text-slate-400" />}
              <span>{isEditable ? "View Mode" : "Edit Code"}</span>
            </button>
          )}

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Copy script code to clipboard"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span className="hidden sm:inline">{copied ? "Copied" : "Copy"}</span>
          </button>

          {onSaveToSuite && (
            <button
              onClick={handleSave}
              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-300 transition"
              title="Save current script into Test Suite"
            >
              <BookmarkPlus className="w-3.5 h-3.5 text-indigo-400" />
              <span className="hidden sm:inline">Save Suite</span>
            </button>
          )}

          {/* Primary Direct Run Button */}
          {onRunScript && (
            <button
              onClick={handleRun}
              disabled={isValidating || !displayCode}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-lg transition shadow-md ${
                isValidating || !displayCode
                  ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/40 active:scale-95 ring-1 ring-emerald-400/50"
              }`}
              title="Directly execute and validate this Playwright script in Chromium"
            >
              {isValidating ? (
                <>
                  <RotateCcw className="w-3 h-3 animate-spin text-emerald-300" />
                  <span>Validating...</span>
                </>
              ) : (
                <>
                  <Play className="w-3 h-3 fill-current text-emerald-100" />
                  <span>▶ Run Script to Validate</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Editor or Formatted Code View */}
      <div className="flex-1 p-3 overflow-auto max-h-[380px] bg-slate-950/90 font-mono text-xs text-slate-300">
        {activeTab === "diagnosis" && diagnosis ? (
          <div className="space-y-3 p-1">
            <div className="p-3.5 rounded-lg bg-amber-950/20 border border-amber-800/40">
              <h4 className="text-amber-400 font-bold text-xs uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" /> Root Cause Analysis
              </h4>
              <p className="text-slate-200 text-xs leading-relaxed">{diagnosis.root_cause || "Analyzing failure..."}</p>
            </div>

            <div className="p-3.5 rounded-lg bg-violet-950/20 border border-violet-800/40">
              <h4 className="text-violet-400 font-bold text-xs uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-violet-400" /> Adaptive Repair Action
              </h4>
              <p className="text-slate-200 text-xs leading-relaxed">{diagnosis.recommended_fix || "Applying self-healing patch..."}</p>
            </div>

            {diagnosis.diff_summary && (
              <div className="p-3.5 rounded-lg bg-cyan-950/20 border border-cyan-800/40">
                <h4 className="text-cyan-400 font-bold text-xs uppercase tracking-wider mb-1">
                  Code Modifications
                </h4>
                <p className="text-slate-200 text-xs">{diagnosis.diff_summary}</p>
              </div>
            )}
          </div>
        ) : isEditable ? (
          <textarea
            value={editableCode}
            onChange={(e) => setEditableCode(e.target.value)}
            rows={18}
            placeholder="# Enter or modify Python Playwright script here..."
            className="w-full h-full min-h-[340px] bg-slate-950 text-emerald-300 font-mono text-xs p-2 rounded-lg border border-slate-800 focus:outline-none focus:border-cyan-500 resize-none leading-relaxed"
          />
        ) : (
          <pre className="whitespace-pre-wrap leading-relaxed select-text">
            <code>{displayCode || "# No script generated yet. Enter target URL or select a preset to generate."}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
