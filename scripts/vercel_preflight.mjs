/** Fail-closed validation of the user-approved free deployment target. */
export const approvedTarget = Object.freeze({
  teamId: "team_vX4hl0qHhzt1aKFxd5wVJ7bU",
  teamSlug: "testing-group1",
  project: "outskill-group2-browser-studio",
  sdkVersion: "3.6.1",
});

export function verifyFreeTarget(account, expectedSlug) {
  if (!account || account.id !== approvedTarget.teamId ||
      account.slug !== expectedSlug || expectedSlug !== approvedTarget.teamSlug ||
      account.plan !== "hobby") {
    throw new Error("Free deployment preflight rejected this account or plan; no resources were created.");
  }
}

/** This probe uses no app data or API keys and deletes its own restore points. */
export async function probePersistentSandbox({ Sandbox, account, projectId, name, credentials }) {
  verifyFreeTarget(account, approvedTarget.teamSlug);
  if (!/^prj_[a-zA-Z0-9]+$/.test(projectId) || !/^group2-capability-probe-[a-z0-9-]+$/.test(name)) {
    throw new Error("Free deployment preflight rejected a non-disposable probe target.");
  }
  if (!credentials?.token || credentials.teamId !== account.id || credentials.projectId !== projectId) {
    throw new Error("Free deployment preflight rejected unscoped Sandbox credentials.");
  }
  const content = "Group2 synthetic persistence probe; no application data.\n";
  let sandbox;
  try {
    sandbox = await Sandbox.create({
      ...credentials, name, image: "vercel/sandbox/universal", timeout: 120_000,
      resources: { vcpus: 1 }, persistent: true, snapshotExpiration: 0,
      keepLastSnapshots: { count: 1, expiration: 0, deleteEvicted: true },
      networkPolicy: "deny-all",
    });
    if (!sandbox.persistent || sandbox.snapshotExpiration !== 0 ||
        sandbox.keepLastSnapshots?.count !== 1 || !sandbox.keepLastSnapshots?.deleteEvicted) {
      throw new Error("Free persistent Sandbox retention controls are unavailable.");
    }
    await sandbox.writeFiles([{ path: "/vercel/sandbox/group2-probe.txt", content: Buffer.from(content) }]);
    const stopped = await sandbox.stop();
    const snapshotId = stopped.snapshot?.id ?? sandbox.currentSnapshotId;
    if (!snapshotId) throw new Error("Persistent Sandbox did not create a restore point.");
    const resumed = await Sandbox.get({ ...credentials, name, resume: true });
    const restored = await resumed.readFileToBuffer({ path: "/vercel/sandbox/group2-probe.txt" });
    if (!restored || restored.toString() !== content) {
      throw new Error("Synthetic file failed persistence verification.");
    }
    sandbox = resumed;
    return { projectId, name, sdkVersion: approvedTarget.sdkVersion, image: sandbox.image,
      snapshotId, persisted: true, accountPlan: account.plan, checkedAt: new Date().toISOString() };
  } finally {
    if (sandbox) await sandbox.delete({ deleteOrphanSnapshots: true });
  }
}
