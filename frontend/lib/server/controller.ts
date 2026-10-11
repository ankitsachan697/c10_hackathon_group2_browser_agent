import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { Sandbox } from "@vercel/sandbox";
import { getVercelOidcToken } from "@vercel/oidc";
import type { CloudSettings } from "./cloudSettings";

export type ControllerHandle = { name: string; origin: string; expiresAt: string; sourceRevision: string };
type Bootstrap = (settings: CloudSettings) => Promise<ControllerHandle>;
const inflight = new Map<string, Promise<ControllerHandle>>();

type PersistentOptions = Parameters<typeof Sandbox.create>[0] & { name: string };
type PersistentSDK<T> = {
  get: (params: PersistentOptions & { resume: true }) => Promise<T>;
  create: (params: PersistentOptions) => Promise<T>;
};
export function getPersistentController(params: PersistentOptions): Promise<Sandbox>;
export function getPersistentController<T>(params: PersistentOptions, sdk: PersistentSDK<T>): Promise<T>;
export async function getPersistentController(params: PersistentOptions, sdk: PersistentSDK<unknown> = Sandbox): Promise<unknown> {
  try {
    return await sdk.get({ ...params, resume: true });
  } catch (error) {
    const failure = error as { response?: { status?: number }; json?: { error?: { code?: string } } };
    if (failure.response?.status === 404 && failure.json?.error?.code === "not_found") return sdk.create(params);
    // A failed restore, permission error, quota failure or network error must
    // retain the existing workspace. Never delete it or initialize a new DB.
    throw error;
  }
}

export async function prepareControllerState(sandbox: { runCommand: (cmd: string, args: string[]) => Promise<{ exitCode: number | null }> }): Promise<void> {
  const result = await sandbox.runCommand("python", ["-c", "import pathlib; pathlib.Path('/vercel/sandbox/state').mkdir(parents=True,exist_ok=True,mode=0o700)"]);
  if (result.exitCode !== 0) throw new Error("Controller state initialization failed");
}

export async function ensureController(settings: CloudSettings, boot: Bootstrap = bootstrapController): Promise<ControllerHandle> {
  const key = `${settings.controllerName}:${settings.sourceRevision}`;
  let pending = inflight.get(key);
  if (!pending) {
    pending = boot(settings);
    inflight.set(key, pending);
    void pending.finally(() => { if (inflight.get(key) === pending) inflight.delete(key); }).catch(() => {});
  }
  return pending;
}

async function bootstrapController(settings: CloudSettings): Promise<ControllerHandle> {
  const token = await getVercelOidcToken({ team: settings.teamId, project: settings.projectId });
  const claims = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());
  if (claims.owner_id !== settings.teamId || claims.project_id !== settings.projectId || claims.exp * 1000 < Date.now() + 600_000) {
    throw new Error("Scoped Vercel credentials are expired or lack the required job budget");
  }
  const credentials = { token, teamId: settings.teamId, projectId: settings.projectId };
  const sandbox = await getPersistentController({
    ...credentials, name: settings.controllerName,
    image: settings.image, persistent: true, snapshotExpiration: 0,
    keepLastSnapshots: { count: 1, expiration: 0, deleteEvicted: true },
    resources: { vcpus: 1 }, ports: [8000], timeout: settings.sessionMinutes * 60_000,
    // Trusted controller installs dependencies and calls n8n/Vercel only.
    networkPolicy: { allow: ["pypi.org", "files.pythonhosted.org", "api.vercel.com", "outskilltraining.app.n8n.cloud"] },
  });
  if (!sandbox.persistent || sandbox.snapshotExpiration !== 0) throw new Error("Controller persistence policy differs from the approved policy");
  const origin = sandbox.domain(8000);
  const archive = await readFile(settings.runtimePath);
  const hash = createHash("sha256").update(archive).digest("hex");
  const upload = `/vercel/sandbox/incoming-${randomUUID()}.tar.gz`;
  const state = "/vercel/sandbox/state";
  const credentialUpload = `${state}/sdk-${randomUUID()}.json`;
  const release = `/vercel/sandbox/releases/${hash}`;
  await prepareControllerState(sandbox);
  await sandbox.writeFiles([
    { path: upload, content: archive },
    { path: credentialUpload, content: Buffer.from(JSON.stringify({ token })) },
  ]);
  const credentialUpdate = await sandbox.runCommand("python", ["-c",
    "import os,sys; os.chmod(sys.argv[1],0o600); os.replace(sys.argv[1],sys.argv[2])", credentialUpload, `${state}/sdk-credentials.json`]);
  if (credentialUpdate.exitCode !== 0) throw new Error("Private SDK credential refresh failed");
  // Unpack the standard-library bootstrap under its own in-VM lock; no local
  // history, .env, keys or app credentials exist in this allowlisted tarball.
  const unpack = await sandbox.runCommand({ cmd: "python", args: ["-c",
    "import fcntl,tarfile,pathlib,sys; root=pathlib.Path(sys.argv[2]); root.mkdir(parents=True,exist_ok=True); lock=open('/vercel/sandbox/state/package.lock','a'); fcntl.flock(lock,fcntl.LOCK_EX); tarfile.open(sys.argv[1]).extractall(root,filter='data')",
    upload, release], timeoutMs: 30_000 });
  if (unpack.exitCode !== 0) throw new Error("Controller runtime unpack failed");
  const boot = await sandbox.runCommand({ cmd: "python", args: [
    `${release}/backend/cloud_lifecycle.py`, "--release-root", release, "--state-root", state,
    "--revision", settings.sourceRevision,
  ], env: {
    CLOUD_MODE: "true", CLOUD_STATE_ROOT: state, CLOUD_CONTROL_SECRET: settings.controlSecret,
    CLOUD_MEDIA_SECRET: settings.mediaSecret, COMPANION_ADMIN_TOKEN: settings.companionToken,
    N8N_BEARER_TOKEN: settings.n8nToken, VERCEL_TEAM_ID: settings.teamId, VERCEL_PROJECT_ID: settings.projectId,
    CLOUD_CONTROLLER_ORIGIN: origin, CLOUD_SESSION_EXPIRES_AT: sandbox.expiresAt?.toISOString() ?? "",
    CLOUD_SESSION_ID: sandbox.currentSession().sessionId,
    CLOUD_WORKER_IMAGE: settings.image, RUNNER_BROWSER_LOCATION: "hosted", RUNNER_RELAY_BASE_URL: origin,
  }, timeoutMs: 180_000 });
  if (boot.exitCode !== 0) throw new Error("Controller startup failed; configuration or free quota needs attention");
  const ready = JSON.parse(await boot.stdout());
  if (!ready.ready) throw new Error("Controller is not ready");
  // The upload is disposable source, never a runtime state/restore point.
  await sandbox.runCommand("python", ["-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).unlink(missing_ok=True)", upload]);
  return { name: settings.controllerName, origin, expiresAt: sandbox.expiresAt?.toISOString() ?? "", sourceRevision: settings.sourceRevision };
}
