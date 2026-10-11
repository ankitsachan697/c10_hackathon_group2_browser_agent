// @vitest-environment node
import { describe, expect, it } from "vitest";
import { loadCloudSettings } from "@/lib/server/cloudSettings";
import { ensureController, prepareControllerState } from "@/lib/server/controller";

describe("protected cloud controller", () => {
  const env = {
    CLOUD_MODE: "true", VERCEL_ENV: "preview", VERCEL_PROJECT_ID: "prj_AKsTYfYD7rX5t29TUCn440Yr6Dsq",
    VERCEL_TEAM_ID: "team_vX4hl0qHhzt1aKFxd5wVJ7bU",
    CLOUD_CONTROL_SECRET: "synthetic-controller-secret-32-bytes",
    CLOUD_MEDIA_SECRET: "synthetic-media-secret-of-32-bytes",
    COMPANION_ADMIN_TOKEN: "synthetic-companion-admin-32-bytes",
    VERCEL_GIT_COMMIT_SHA: "1234567890abcdef1234567890abcdef12345678",
  };

  it("concurrentBootstrapStartsOneProcess", async () => {
    const settings = loadCloudSettings(env)!;
    let starts = 0;
    const boot = async () => {
      starts++;
      await new Promise((resolve) => setTimeout(resolve, 15));
      return { name: settings.controllerName, origin: "https://synthetic.vercel.run", expiresAt: new Date(Date.now() + 600_000).toISOString(), sourceRevision: settings.sourceRevision };
    };
    const [one, two] = await Promise.all([ensureController(settings, boot), ensureController(settings, boot)]);
    expect(starts).toBe(1);
    expect(one).toEqual(two);
  });

  it("preview and production preserve distinct stable identities across source revisions", () => {
    const preview = loadCloudSettings(env)!;
    const updated = loadCloudSettings({ ...env, VERCEL_GIT_COMMIT_SHA: "abcdef1234567890abcdef1234567890abcdef12" })!;
    const production = loadCloudSettings({ ...env, VERCEL_ENV: "production" })!;
    expect(preview.controllerName).toBe(updated.controllerName);
    expect(production.controllerName).not.toBe(preview.controllerName);
  });

  it("cloud configuration cannot fall back to an unsecured local backend", () => {
    expect(() => loadCloudSettings({ ...env, CLOUD_CONTROL_SECRET: "" })).toThrow(/CLOUD_CONTROL_SECRET/);
    expect(() => loadCloudSettings({ ...env, VERCEL_TEAM_ID: "wrong" })).toThrow(/account/);
    expect(loadCloudSettings({})).toBeNull();
  });

  it("creates the controller state recursively in a fresh image", async () => {
    const calls: unknown[][] = [];
    await prepareControllerState({ runCommand: async (...args: unknown[]) => { calls.push(args); return { exitCode: 0 }; } });
    expect(calls[0][0]).toBe("python");
    expect(calls[0][1]).toEqual(["-c", "import pathlib; pathlib.Path('/vercel/sandbox/state').mkdir(parents=True,exist_ok=True,mode=0o700)"]);
  });
});
