"use client";

import { useState } from "react";
import Image from "next/image";
import type { Artifact } from "@/lib/types";

function MediaCard({ artifact, kind }: { artifact: Artifact; kind: "screenshot" | "video" }) {
  const [unavailable, setUnavailable] = useState(false);
  const title = artifact.storage_path.split("/").pop() || (kind === "video" ? "Recording" : "Screenshot");
  const src = `/api/artifacts/${encodeURIComponent(artifact.id)}`;
  const validType = !artifact.media_type || (kind === "screenshot" ? artifact.media_type.startsWith("image/") : artifact.media_type.startsWith("video/"));
  return <article className="media-card"><div className="media-preview">
    {!validType || unavailable ? <p className="muted">Preview unavailable. Open the artifact to inspect it.</p> : kind === "screenshot" ? <Image src={src} alt={title} width={1280} height={800} unoptimized onError={() => setUnavailable(true)}/> : <video src={src} controls preload="metadata" onError={() => setUnavailable(true)}>Your browser cannot play this recording.</video>}
  </div><div className="media-caption"><strong>{title}</strong><a href={src} target="_blank" rel="noreferrer">Open artifact</a></div></article>;
}

export function RunMedia({ artifacts, kind }: { artifacts: Artifact[]; kind: "screenshot" | "video" }) {
  const matching = artifacts.filter(artifact => artifact.kind === kind);
  if (!matching.length) return <p className="evidence-empty">{kind === "screenshot" ? "No screenshots captured yet." : "No recording captured yet."}</p>;
  return <div className="media-grid">{matching.map(artifact => <MediaCard key={artifact.id} artifact={artifact} kind={kind}/>)}</div>;
}
