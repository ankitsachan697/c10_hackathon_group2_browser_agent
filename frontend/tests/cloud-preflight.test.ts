import { describe, expect, it } from "vitest";
import { verifyFreeTarget, probePersistentSandbox } from "../../scripts/vercel_preflight.mjs";

async function verify(account: object) {
  return verifyFreeTarget(account, "testing-group1");
}

describe("free cloud preflight", () => {
  it("accepts only the approved Hobby account", async () => {
    await expect(verify({ id: "team_vX4hl0qHhzt1aKFxd5wVJ7bU", slug: "testing-group1", plan: "hobby" })).resolves.toBeUndefined();
  });

  it.each([
    { id: "team_vX4hl0qHhzt1aKFxd5wVJ7bU", slug: "testing-group1", plan: "pro" },
    { id: "different-team", slug: "testing-group1", plan: "hobby" },
    { id: "team_vX4hl0qHhzt1aKFxd5wVJ7bU", slug: "wrong-account", plan: "hobby" },
    { id: "team_vX4hl0qHhzt1aKFxd5wVJ7bU", slug: "testing-group1" },
  ])("rejectsNonHobbyOrUnexpectedAccount: %j", async (account) => {
    await expect(verify(account)).rejects.toThrow(/free deployment preflight/i);
  });
});

describe("disposable persistence probe", () => {
  const account = { id: "team_vX4hl0qHhzt1aKFxd5wVJ7bU", slug: "testing-group1", plan: "hobby" };
  const credentials = { teamId: account.id, projectId: "prj_fixture", token: "synthetic-probe-token" };
  it("stops, resumes, verifies synthetic content, then deletes only its probe", async () => {
    let stopped = false;
    let deleted = false;
    let file = "";
    const sandbox = {
      name: "group2-capability-probe-fixture", persistent: true, snapshotExpiration: 0,
      keepLastSnapshots: { count: 1, deleteEvicted: true }, image: "vercel/sandbox/universal",
      writeFiles: async (entries: { content: Buffer }[]) => { file = entries[0].content.toString(); },
      stop: async () => { stopped = true; return { snapshot: { id: "snap_fixture" } }; },
      delete: async () => { deleted = true; },
      readFileToBuffer: async () => Buffer.from(file),
    };
    const Sandbox = {
      create: async () => sandbox,
      get: async () => { if (!stopped) throw Error("not stopped"); return sandbox; },
    };
    const receipt = await probePersistentSandbox({ Sandbox, account, projectId: "prj_fixture", name: sandbox.name, credentials });
    expect(receipt.persisted).toBe(true);
    expect(receipt.snapshotId).toBe("snap_fixture");
    expect(stopped).toBe(true);
    expect(deleted).toBe(true);
  });
  it("never provisions in a non-Hobby account", async () => {
    let created = false;
    await expect(probePersistentSandbox({
      Sandbox: { create: async () => { created = true; } },
      account: { ...account, plan: "pro" }, projectId: "prj_fixture", name: "group2-capability-probe-fixture", credentials,
    })).rejects.toThrow(/free deployment preflight/i);
    expect(created).toBe(false);
  });
  it("cleans up and refuses success when synthetic content is lost", async () => {
    let deleted = false;
    const sandbox = {
      name: "group2-capability-probe-fixture", persistent: true, snapshotExpiration: 0,
      keepLastSnapshots: { count: 1, deleteEvicted: true }, image: "vercel/sandbox/universal",
      writeFiles: async () => {}, stop: async () => ({ snapshot: { id: "snap_fixture" } }),
      readFileToBuffer: async () => Buffer.from("wrong-content"),
      delete: async () => { deleted = true; },
    };
    await expect(probePersistentSandbox({
      Sandbox: { create: async () => sandbox, get: async () => sandbox },
      account, projectId: "prj_fixture", name: sandbox.name, credentials,
    })).rejects.toThrow(/persist/i);
    expect(deleted).toBe(true);
  });
});
