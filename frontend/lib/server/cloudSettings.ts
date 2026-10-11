import path from "node:path";
import applicationConfig from "../../../config/application.json";

export type CloudSettings = {
  teamId: string; projectId: string; environment: "production" | "preview";
  controllerName: string; image: string; sessionMinutes: number; sourceRevision: string;
  runtimePath: string; controlSecret: string; mediaSecret: string;
  companionToken: string; n8nToken: string;
};

export function loadCloudSettings(env: Record<string, string | undefined> = process.env): CloudSettings | null {
  if (env.CLOUD_MODE !== "true") {
    if (env.VERCEL === "1") throw new Error("Cloud controller is not configured; local fallback is disabled on Vercel");
    return null;
  }
  const config = applicationConfig.cloud;
  if ((env.VERCEL_TEAM_ID && env.VERCEL_TEAM_ID !== config.teamId) || (env.VERCEL_PROJECT_ID && env.VERCEL_PROJECT_ID !== config.projectId)) {
    throw new Error("Cloud account/project does not match the approved deployment");
  }
  for (const name of ["CLOUD_CONTROL_SECRET", "CLOUD_MEDIA_SECRET", "COMPANION_ADMIN_TOKEN"]) {
    if ((env[name]?.length ?? 0) < 32) throw new Error(`${name} is not configured privately`);
  }
  const environment = env.VERCEL_ENV === "production" ? "production" : "preview";
  const revision = env.VERCEL_GIT_COMMIT_SHA || env.CLOUD_SOURCE_REVISION;
  if (!revision || !/^[a-f0-9]{40}$/.test(revision)) throw new Error("Cloud source revision is missing or invalid");
  return {
    teamId: config.teamId, projectId: config.projectId, environment,
    controllerName: `group2-${environment}-controller`, image: config.controllerImage,
    sessionMinutes: config.sessionMinutes, sourceRevision: revision,
    runtimePath: path.resolve(process.cwd(), "cloud-runtime/group2-runtime.tar.gz"),
    controlSecret: env.CLOUD_CONTROL_SECRET!, mediaSecret: env.CLOUD_MEDIA_SECRET!,
    companionToken: env.COMPANION_ADMIN_TOKEN!, n8nToken: env.N8N_BEARER_TOKEN ?? "",
  };
}
