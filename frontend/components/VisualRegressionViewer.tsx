"use client";

import React, { useState } from "react";
import {
  Eye,
  CheckCircle2,
  AlertOctagon,
  Layers,
  Maximize2,
  X,
  Video,
  Award,
  SlidersHorizontal,
  ExternalLink,
} from "lucide-react";

export interface VisualDiffData {
  status: string;
  passed: boolean;
  is_first_run?: boolean;
  baseline_key?: string;
  mismatched_pixels?: number;
  mismatch_percentage?: number;
  tolerance_threshold?: number;
  summary: string;
  diff_image?: string;
  baseline_image?: string;
  candidate_image?: string;
}

interface Props {
  diffData?: VisualDiffData | null;
  screenshots?: string[];
  video?: string | null;
  backendUrl?: string;
  runId?: string;
}

export function VisualRegressionViewer({
  diffData,
  screenshots,
  video,
  backendUrl = "http://127.0.0.1:8000",
  runId,
}: Props) {
  const [modalImage, setModalImage] = useState<{ url: string; title: string } | null>(null);
  const [activeDiffTab, setActiveDiffTab] = useState<"diff" | "baseline" | "candidate">("diff");
  const [videoError, setVideoError] = useState(false);

  const getPrimaryUrl = (s: string) => {
    if (s.startsWith("http://") || s.startsWith("https://")) return s;
    if (s.startsWith("baselines/")) return `${backendUrl}/api/artifacts/${s}`;
    return runId ? `${backendUrl}/api/artifacts/${runId}/${s}` : `${backendUrl}/api/artifacts/${s}`;
  };

  const getFallbackUrl = (s: string) => {
    return `${backendUrl}/api/artifacts/${s}`;
  };

  const videoUrl = video
    ? runId
      ? `${backendUrl}/api/artifacts/${runId}/${video}`
      : `${backendUrl}/api/artifacts/${video}`
    : null;

  const isFirstRun = diffData?.is_first_run || diffData?.status === "BASELINE_ESTABLISHED";

  return (
    <div className="flex flex-col bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800 gap-2">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-pink-400" />
          <span className="font-mono text-xs font-semibold tracking-wider text-slate-200">
            VISUAL REGRESSION MONITOR (PIXELMATCH) & VIDEO RECORDING
          </span>
        </div>

        {diffData && (
          <div className="flex items-center gap-2">
            {isFirstRun ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-950/90 text-indigo-300 border border-indigo-700/80 shadow">
                <Award className="w-3.5 h-3.5 text-indigo-400" />
                GOLDEN BASELINE ESTABLISHED
              </span>
            ) : (
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  diffData.passed
                    ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800"
                    : "bg-red-950/80 text-red-400 border border-red-800 animate-pulse"
                }`}
              >
                {diffData.passed ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5" /> PASSED ({diffData.mismatch_percentage}%)
                  </>
                ) : (
                  <>
                    <AlertOctagon className="w-3.5 h-3.5" /> REGRESSION DETECTED ({diffData.mismatch_percentage}%)
                  </>
                )}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Golden Baseline or Regression Banner */}
      {diffData && (
        <div
          className={`px-4 py-2.5 text-xs border-b flex items-start gap-2 ${
            isFirstRun
              ? "bg-indigo-950/30 border-indigo-900/50 text-indigo-200"
              : diffData.passed
              ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-300"
              : "bg-red-950/20 border-red-900/40 text-red-300"
          }`}
        >
          {isFirstRun ? (
            <div className="flex items-start gap-2">
              <Award className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-indigo-300">Smart Baseline Initialized: </span>
                {diffData.summary}
              </div>
            </div>
          ) : (
            <div>{diffData.summary}</div>
          )}
        </div>
      )}

      {/* Main Grid: Diff Viewer + Video + Screenshots */}
      <div className="p-4 space-y-5">
        {/* Visual Diff Comparison Box if Subsequent Run */}
        {diffData && !isFirstRun && diffData.diff_image && (
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2">
              <span className="text-xs font-mono font-semibold text-slate-300 flex items-center gap-1.5">
                <SlidersHorizontal className="w-3.5 h-3.5 text-pink-400" />
                PIXELMATCH HEATMAP COMPARISON
              </span>
              <div className="flex rounded-lg bg-slate-950 p-0.5 border border-slate-800 text-xs">
                <button
                  onClick={() => setActiveDiffTab("diff")}
                  className={`px-2.5 py-1 rounded transition ${
                    activeDiffTab === "diff"
                      ? "bg-pink-950/90 text-pink-300 font-bold border border-pink-700/60"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Magenta Diff Heatmap
                </button>
                {diffData.baseline_image && (
                  <button
                    onClick={() => setActiveDiffTab("baseline")}
                    className={`px-2.5 py-1 rounded transition ${
                      activeDiffTab === "baseline"
                        ? "bg-indigo-950/90 text-indigo-300 font-bold border border-indigo-700/60"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Golden Baseline
                  </button>
                )}
                {diffData.candidate_image && (
                  <button
                    onClick={() => setActiveDiffTab("candidate")}
                    className={`px-2.5 py-1 rounded transition ${
                      activeDiffTab === "candidate"
                        ? "bg-slate-800 text-slate-100 font-bold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Current Candidate
                  </button>
                )}
              </div>
            </div>

            <div className="aspect-[16/9] max-h-[360px] w-full bg-slate-950 rounded-lg overflow-hidden relative flex items-center justify-center border border-slate-800">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={
                  activeDiffTab === "diff"
                    ? getPrimaryUrl(diffData.diff_image)
                    : activeDiffTab === "baseline" && diffData.baseline_image
                    ? getPrimaryUrl(diffData.baseline_image)
                    : diffData.candidate_image
                    ? getPrimaryUrl(diffData.candidate_image)
                    : getPrimaryUrl(diffData.diff_image)
                }
                alt="Diff View"
                className="max-h-full max-w-full object-contain cursor-pointer hover:scale-[1.02] transition"
                onClick={() =>
                  setModalImage({
                    url: getPrimaryUrl(
                      activeDiffTab === "diff"
                        ? diffData.diff_image!
                        : activeDiffTab === "baseline" && diffData.baseline_image
                        ? diffData.baseline_image
                        : diffData.candidate_image!
                    ),
                    title: `Visual Regression - ${activeDiffTab.toUpperCase()}`,
                  })
                }
              />
            </div>
          </div>
        )}

        {/* Video Session Recording Player */}
        {videoUrl ? (
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Video className="w-3.5 h-3.5 text-cyan-400" />
                PLAYWRIGHT SESSION VIDEO RECORDING (.WEBM)
              </h4>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
                  1280x800 Chromium Session
                </span>
                <a
                  href={videoUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] font-mono text-slate-400 hover:text-cyan-300 flex items-center gap-1 bg-slate-800 px-2 py-0.5 rounded transition"
                  title="Open video directly in new browser tab"
                >
                  <ExternalLink className="w-2.5 h-2.5" /> Open / Download
                </a>
              </div>
            </div>

            <div className="rounded-lg overflow-hidden bg-slate-950 border border-slate-800 max-h-[380px] flex items-center justify-center p-1">
              <video
                key={videoUrl}
                src={videoUrl}
                controls
                playsInline
                preload="auto"
                onError={() => setVideoError(true)}
                className="w-full max-h-[380px] rounded-md object-contain"
              >
                Your browser does not support WebM video playback.
              </video>
            </div>
            {videoError && (
              <p className="text-[11px] text-amber-400 text-center">
                Video is being finalized or buffered. You can also click &quot;Open / Download&quot; above.
              </p>
            )}
          </div>
        ) : null}

        {/* Screenshots Gallery */}
        {screenshots && screenshots.length > 0 ? (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" /> Journey Screenshots Captured ({screenshots.length})
              </h4>
              <span className="text-[11px] text-slate-500 font-mono">Click any screenshot to zoom</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
              {screenshots.map((s, idx) => {
                const primaryUrl = getPrimaryUrl(s);
                const fallbackUrl = getFallbackUrl(s);

                return (
                  <div
                    key={idx}
                    onClick={() => setModalImage({ url: primaryUrl, title: s })}
                    className="group relative rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden hover:border-cyan-500/50 hover:shadow-lg hover:shadow-cyan-500/10 transition-all cursor-pointer"
                  >
                    <div className="aspect-[16/10] w-full bg-slate-950 relative flex items-center justify-center overflow-hidden">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={primaryUrl}
                        alt={s}
                        className="object-cover w-full h-full group-hover:scale-105 transition duration-300"
                        onError={(e) => {
                          if (e.currentTarget.src !== fallbackUrl) {
                            e.currentTarget.src = fallbackUrl;
                          }
                        }}
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                        <span className="px-2.5 py-1 rounded-md bg-slate-900/90 text-cyan-300 text-xs font-mono flex items-center gap-1 border border-cyan-500/30">
                          <Maximize2 className="w-3 h-3" /> View Screenshot
                        </span>
                      </div>
                    </div>
                    <div className="p-2 text-xs font-mono text-slate-300 truncate bg-slate-900 border-t border-slate-800 flex items-center justify-between">
                      <span className="truncate">{s}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          !diffData && (
            <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500">
              <Eye className="w-8 h-8 text-slate-700 mb-2" />
              <p className="text-xs">No screenshots captured yet.</p>
              <p className="text-[11px] text-slate-600">Run an execution flow to trigger visual regression testing.</p>
            </div>
          )
        )}
      </div>

      {/* Enlarged Screenshot Modal */}
      {modalImage && (
        <div
          onClick={() => setModalImage(null)}
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-slate-900 border border-slate-700 rounded-2xl max-w-5xl w-full max-h-[90vh] flex flex-col overflow-hidden shadow-2xl"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950">
              <span className="font-mono text-xs text-cyan-400 font-semibold">{modalImage.title}</span>
              <button
                onClick={() => setModalImage(null)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-3 bg-slate-950 flex-1 overflow-auto flex items-center justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={modalImage.url}
                alt={modalImage.title}
                className="max-h-[75vh] w-auto object-contain rounded-lg border border-slate-800"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
