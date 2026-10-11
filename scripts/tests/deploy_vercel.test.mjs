import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { configureDeployment, stageDeployment } from "../deploy_vercel.mjs";

const target = { teamId: "team_vX4hl0qHhzt1aKFxd5wVJ7bU", teamSlug: "testing-group1", projectId: "prj_AKsTYfYD7rX5t29TUCn440Yr6Dsq", projectName: "outskill-group2-browser-studio" };
const env = { VERCEL_TOKEN: "synthetic-private-vercel", N8N_BEARER_TOKEN: "synthetic-private-n8n", GITHUB_SHA: "a".repeat(40) };

test("deployment refuses a paid account before mutation", async () => {
  const calls = [];
  const api = async (endpoint, options = {}) => { calls.push(options.method ?? "GET"); return { id: target.teamId, slug: target.teamSlug, billing: { plan: "pro" } }; };
  await assert.rejects(configureDeployment(target, env, api), /preflight/);
  assert.deepEqual(calls, ["GET"]);
});

test("private mapping preserves existing stable controller keys and does not expose tokens", async () => {
  const mutations = [];
  const api = async (endpoint, options = {}) => {
    if (options.method) { mutations.push({ endpoint, ...options }); return {}; }
    if (endpoint.includes("/teams/")) return { id: target.teamId, slug: target.teamSlug, billing: { plan: "hobby" } };
    if (endpoint.includes("/env")) return { envs: ["CLOUD_CONTROL_SECRET", "CLOUD_MEDIA_SECRET", "COMPANION_ADMIN_TOKEN"].map(key => ({ key, target: ["production", "preview"], type: "sensitive" })) };
    return { id: target.projectId, name: target.projectName, ssoProtection: { deploymentType: "all_except_custom_domains" } };
  };
  await configureDeployment(target, env, api);
  const variables = mutations.find(call => call.endpoint.includes("/env")).body;
  assert.equal(variables.find(item => item.key === "N8N_BEARER_TOKEN").value, env.N8N_BEARER_TOKEN);
  assert.equal(variables.find(item => item.key === "N8N_BEARER_TOKEN").type, "sensitive");
  assert.equal(variables.some(item => item.key === "VERCEL_TOKEN"), false);
  assert.equal(variables.some(item => item.key === "CLOUD_CONTROL_SECRET"), false);
  assert.equal(variables.some(item => item.key.startsWith("NEXT_PUBLIC_")), false);
  assert.equal(mutations.some(call => call.body?.ssoProtection === null), false);
});

test("deployment source staging excludes local history and credentials", () => {
  const root = mkdtempSync(path.join(tmpdir(), "group2-source-fixture-"));
  const output = mkdtempSync(path.join(tmpdir(), "group2-deploy-fixture-"));
  for (const directory of ["frontend/app", "frontend/components", "frontend/lib", "frontend/public", "frontend/cloud-runtime", "config", "artifacts"]) mkdirSync(path.join(root, directory), { recursive: true });
  for (const name of ["package.json", "package-lock.json", "tsconfig.json", "next.config.ts", "next-env.d.ts", "eslint.config.mjs"]) writeFileSync(path.join(root, "frontend", name), "{}");
  writeFileSync(path.join(root, "config/application.json"), JSON.stringify({ cloud: target }));
  writeFileSync(path.join(root, "frontend/cloud-runtime/group2-runtime.tar.gz"), "synthetic runtime");
  writeFileSync(path.join(root, "frontend/.env.local"), "private");
  writeFileSync(path.join(root, "frontend/app/.env"), "private");
  writeFileSync(path.join(root, "artifacts/private.txt"), "private");
  stageDeployment(root, output, target);
  assert.equal(existsSync(path.join(output, "frontend/.env.local")), false);
  assert.equal(existsSync(path.join(output, "frontend/app/.env")), false);
  assert.equal(existsSync(path.join(output, "artifacts")), false);
  assert.equal(existsSync(path.join(output, "frontend/cloud-runtime/group2-runtime.tar.gz")), true);
  assert.equal(existsSync(path.join(output, ".vercel/project.json")), true);
});
