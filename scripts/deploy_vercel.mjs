/** Private GitHub-to-Vercel setup and allowlisted deployment packaging. */
import { randomBytes } from "node:crypto";
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { approvedTarget, verifyFreeTarget } from "./vercel_preflight.mjs";

export async function configureDeployment(target, env, api) {
  if (!env.VERCEL_TOKEN || !env.N8N_BEARER_TOKEN || !/^[a-f0-9]{40}$/.test(env.GITHUB_SHA ?? "")) {
    throw Error("Required private GitHub secrets or trusted source revision are missing");
  }
  const account = await api(`/v2/teams/${target.teamId}`);
  verifyFreeTarget({ ...account, plan: account.billing?.plan ?? account.plan }, target.teamSlug);
  if (target.teamId !== approvedTarget.teamId || target.projectName !== approvedTarget.project) throw Error("Unapproved deployment target");
  const scope = `teamId=${encodeURIComponent(target.teamId)}`;
  const project = await api(`/v9/projects/${target.projectId}?${scope}`);
  if (project.id !== target.projectId || project.name !== target.projectName) throw Error("Deployment project identity differs");
  if (!["all", "all_except_custom_domains"].includes(project.ssoProtection?.deploymentType)) {
    throw Error("Enable free Vercel Authentication for the production URL before deployment");
  }
  const existing = await api(`/v10/projects/${target.projectId}/env?${scope}&decrypt=false`);
  const privateNames = ["CLOUD_CONTROL_SECRET", "CLOUD_MEDIA_SECRET", "COMPANION_ADMIN_TOKEN"];
  const variables = [
    { key: "N8N_BEARER_TOKEN", value: env.N8N_BEARER_TOKEN, type: "sensitive", target: ["production", "preview"] },
    { key: "CLOUD_MODE", value: "true", type: "plain", target: ["production", "preview"] },
    { key: "CLOUD_SOURCE_REVISION", value: env.GITHUB_SHA, type: "plain", target: ["production", "preview"] },
  ];
  for (const environment of ["production", "preview"]) {
    for (const key of privateNames) {
      if (!(existing.envs ?? []).some(item => item.key === key && item.target?.includes(environment) && !item.gitBranch)) {
        variables.push({ key, value: randomBytes(32).toString("hex"), type: "sensitive", target: [environment] });
      }
    }
  }
  await api(`/v10/projects/${target.projectId}/env?${scope}&upsert=true`, { method: "POST", body: variables });
  await api(`/v9/projects/${target.projectId}?${scope}`, { method: "PATCH", body: {
    framework: "nextjs", rootDirectory: "frontend", sourceFilesOutsideRootDirectory: true,
    buildCommand: "npm run build", installCommand: "npm ci", autoExposeSystemEnvs: true,
  } });
  return { accountPlan: "hobby", projectName: target.projectName, privateConfigurationReady: true };
}

export function stageDeployment(repositoryRoot, outputDir, target) {
  const root = path.resolve(repositoryRoot), output = path.resolve(outputDir);
  if (root === output || root.startsWith(output + path.sep) || (existsSync(output) && readdirSync(output).length)) {
    throw Error("Deployment staging requires a dedicated empty directory");
  }
  mkdirSync(output, { recursive: true });
  const allowed = ["frontend/app", "frontend/components", "frontend/lib", "frontend/public",
    "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json",
    "frontend/next.config.ts", "frontend/eslint.config.mjs",
    "frontend/cloud-runtime/group2-runtime.tar.gz", "config/application.json"];
  for (const name of allowed) {
    const source = path.join(root, name), destination = path.join(output, name);
    if (!existsSync(source)) throw Error(`Required deployment source is missing: ${name}`);
    mkdirSync(path.dirname(destination), { recursive: true });
    cpSync(source, destination, { recursive: true, filter(candidate) {
      if (lstatSync(candidate).isSymbolicLink()) throw Error("Deployment source symlinks are forbidden");
      const base = path.basename(candidate);
      return !base.startsWith(".") && !["node_modules", "artifacts", "test_suites"].includes(base);
    } });
  }
  mkdirSync(path.join(output, ".vercel"));
  writeFileSync(path.join(output, ".vercel/project.json"), JSON.stringify({ projectId: target.projectId, orgId: target.teamId, projectName: target.projectName }));
  return output;
}

async function main() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const target = JSON.parse(readFileSync(path.join(root, "config/application.json"), "utf8")).cloud;
  if (process.argv.includes("--stage-only")) {
    const output = stageDeployment(root, mkdtempSync(path.join(tmpdir(), "group2-vercel-deploy-")), target);
    console.log(output);
    return;
  }
  const api = async (endpoint, options = {}) => {
    const response = await fetch(`https://api.vercel.com${endpoint}`, {
      method: options.method ?? "GET", headers: { Authorization: `Bearer ${process.env.VERCEL_TOKEN}`, "Content-Type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: AbortSignal.timeout(30_000),
    });
    // Never echo provider response bodies: validation errors can contain values.
    if (!response.ok) throw Error(`Private Vercel configuration failed (HTTP ${response.status}, ${endpoint.split("?")[0]})`);
    return response.json();
  };
  const configured = await configureDeployment(target, process.env, api);
  console.log(JSON.stringify(configured));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error instanceof Error ? error.message : "Private deployment preparation failed"); process.exitCode = 1; });
}
