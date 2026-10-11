"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import type { Artifact } from "@/lib/types";

function MediaCard({ artifact, kind }: { artifact: Artifact; kind: "screenshot" | "video" }) {
  const [unavailable, setUnavailable] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const playbackPosition = useRef(0);
  const title = artifact.storage_path.split("/").pop() || (kind === "video" ? "Recording" : "Screenshot");
  const src = `/api/artifacts/${encodeURIComponent(artifact.id)}${refresh ? `?refresh=${refresh}` : ""}`;
  function retry(video?: HTMLVideoElement) {
    if (video) playbackPosition.current = video.currentTime || playbackPosition.current;
    if (refresh < 2) setRefresh(refresh + 1);
    else setUnavailable(true);
  }
  const validType = !artifact.media_type || (kind === "screenshot" ? artifact.media_type.startsWith("image/") : artifact.media_type.startsWith("video/"));
  return <article className="media-card"><div className="media-preview">
    {!validType || unavailable ? <p className="muted">Preview unavailable. Open the artifact to inspect it.</p> : kind === "screenshot" ? <Image src={src} alt={title} width={1280} height={800} unoptimized onError={() => retry()}/> : <video key={refresh} src={src} controls preload="metadata" onLoadedMetadata={event => { if (playbackPosition.current) event.currentTarget.currentTime = playbackPosition.current; }} onError={event => retry(event.currentTarget)}>Your browser cannot play this recording.</video>}
  </div><div className="media-caption"><strong>{title}</strong><a href={src} target="_blank" rel="noreferrer">Open artifact</a></div></article>;
}

export function RunMedia({ artifacts, kind }: { artifacts: Artifact[]; kind: "screenshot" | "video" }) {
  const matching = artifacts.filter(artifact => artifact.kind === kind);
  if (!matching.length) return <p className="evidence-empty">{kind === "screenshot" ? "No screenshots captured yet." : "No recording captured yet."}</p>;
  return <div className="media-grid">{matching.map(artifact => <MediaCard key={artifact.id} artifact={artifact} kind={kind}/>)}</div>;
}
