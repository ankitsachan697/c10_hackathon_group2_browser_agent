import type { Run } from "@/lib/types";

export function RunVisual({ run }: { run: Run }) {
  const review = run.visual_review;
  return <section className="card visual-summary">
    <p className="eyebrow">Visual comparison</p>
    <h2>{run.visual_outcome?.replaceAll("_", " ") ?? "Not reviewed"}</h2>
    {review ? <div className="visual-metrics">
      {typeof review.mismatch_percentage === "number" && <p>Changed pixels: <strong>{review.mismatch_percentage}%</strong></p>}
      {typeof review.agent_status === "string" && <p>Visual agent: <strong>{review.agent_status}</strong></p>}
      {typeof review.agent_summary === "string" && <p>{review.agent_summary}</p>}
      {typeof review.reason === "string" && <p>{review.reason}</p>}
      {typeof review.diff_artifact_id === "string" && <a className="button button-secondary" href={`/api/artifacts/${review.diff_artifact_id}`} target="_blank" rel="noreferrer">Open difference image</a>}
    </div> : <p className="muted">A screenshot is needed to compare this run with a saved baseline.</p>}
    {review && <div className="visual-triptych">{([["baseline_artifact_id", "Baseline screenshot"], ["candidate_artifact_id", "Current screenshot"], ["diff_artifact_id", "Difference heatmap"]] as const).map(([key, label]) => typeof review[key] === "string" && <figure key={key}><figcaption>{label}</figcaption><a href={`/api/artifacts/${review[key]}`} target="_blank" rel="noreferrer">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/api/artifacts/${review[key]}`} alt={label}/></a></figure>)}</div>}
    <p className="muted">Compares the first captured screenshot against the locked baseline. Open an image to inspect it at full size.</p>
    <p className="muted">Functional test status is kept separate from visual review.</p>
  </section>;
}
