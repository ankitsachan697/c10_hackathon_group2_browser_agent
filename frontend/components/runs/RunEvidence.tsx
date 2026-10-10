import type { Artifact } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { RunMedia } from "@/components/runs/RunMedia";

export function RunEvidence({ artifacts = [] }: { artifacts?: Artifact[] }) {
  if (!artifacts.length) return <EmptyState title="No evidence captured" detail="Screenshots, recordings, and logs appear here when available."/>;
  const other = artifacts.filter(artifact => !["screenshot", "video"].includes(artifact.kind));
  return <div className="evidence-stack"><h2>Screenshots</h2><RunMedia artifacts={artifacts} kind="screenshot"/><h2>Recording</h2><RunMedia artifacts={artifacts} kind="video"/>{other.length > 0 && <div className="evidence-grid">{other.map(artifact => <a className="evidence-card" key={artifact.id} href={`/api/artifacts/${encodeURIComponent(artifact.id)}`} target="_blank" rel="noreferrer"><span>{artifact.kind}</span><strong>{artifact.storage_path.split("/").pop()}</strong></a>)}</div>}</div>;
}
