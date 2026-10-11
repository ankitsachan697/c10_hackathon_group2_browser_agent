import { expect, test } from "@playwright/test";

const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8100";

test("saved journeys run directly, remain inspectable, schedulable, and deletable", async ({ page, request }) => {
  const projectResponse = await request.post(`${apiBase}/api/projects`, { data: { name: "Checkout coverage", description: "Critical saved journeys" } });
  expect(projectResponse.ok()).toBeTruthy();
  const project = (await projectResponse.json()).data;
  const journeyResponse = await request.post(`${apiBase}/api/journeys`, { data: {
    project_id: project.id,
    name: "Saved checkout journey",
    target_url: "https://application-under-test.invalid",
    objective: "Validate checkout",
    script: "print('saved script passed')",
  } });
  const journey = (await journeyResponse.json()).data;
  const scheduleResponse = await request.post(`${apiBase}/api/schedules`, { data: {
    journey_id: journey.id, local_time: "09:30", timezone: "Asia/Kolkata",
  } });
  expect(scheduleResponse.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.getByRole("img", { name: "Outskill" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Automation at a glance" })).toBeVisible();

  await page.getByRole("link", { name: "Projects" }).click();
  await expect(page.getByText("Checkout coverage")).toBeVisible();
  await page.getByRole("button", { name: "Project actions" }).click();
  await page.getByRole("menuitem", { name: "Run now" }).click();
  await expect(page.getByText("Executed 1 saved scripts")).toBeVisible();
  await page.getByRole("button", { name: "Close project" }).click();

  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page.getByText("PASSED")).toBeVisible();
  await page.locator("tbody a").first().click();
  await expect(page.getByRole("heading", { name: "Passed" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run current script" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run this version" })).toBeVisible();

  await page.getByRole("link", { name: "Schedules" }).click();
  await expect(page.getByText("Asia/Kolkata")).toBeVisible();
  await page.getByRole("button", { name: "Run now" }).click();
  await expect(page.getByText("Scheduled scope started")).toBeVisible();

  await page.getByRole("link", { name: "Projects" }).click();
  await page.getByRole("button", { name: "Project actions" }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("journeys");
  await dialog.getByRole("button", { name: "Delete project" }).click();
  await expect(page.getByText("Project moved to trash")).toBeVisible();
});

test("journey generation waits for explicit review confirmation", async ({ page }) => {
  let generationCalls = 0;
  await page.route("**/api/projects", route => route.fulfill({ json: { data: [{ id: "project-1", name: "Web journeys" }], error: null, meta: {} } }));
  await page.route("**/api/journeys/generate", route => {
    generationCalls += 1;
    return route.fulfill({ status: 201, json: { data: { script: "print('generated')" }, error: null, meta: {} } });
  });
  await page.goto("/journeys/new");
  await page.getByLabel("Journey name").fill("Sign in");
  await page.getByLabel("Target URL").fill("https://application-under-test.invalid");
  await page.getByLabel("Objective").fill("Sign in and verify the account overview");
  await page.getByRole("button", { name: "Review journey" }).click();
  expect(generationCalls).toBe(0);
  await page.getByRole("button", { name: "Review journey" }).click();
  expect(generationCalls).toBe(0);
  await page.getByRole("button", { name: "Generate and save" }).click();
  await expect(page.getByRole("heading", { name: "Script ready" })).toBeVisible();
  expect(generationCalls).toBe(1);
});

test("navigation remains usable at mobile width with visible keyboard focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  await expect(focused).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Automation at a glance" })).toBeVisible();
});

test("first-time secure login journey executes with complete evidence", async ({ page, request }) => {
  const username = process.env.E2E_LOGIN_USERNAME;
  const password = process.env.E2E_LOGIN_PASSWORD;
  test.skip(!username || !password, "Set E2E_LOGIN_USERNAME and E2E_LOGIN_PASSWORD for the live login acceptance test");

  await page.goto("/journeys/new");
  await page.getByRole("button", { name: "Create first project" }).click();
  await page.getByLabel("Project name").fill("Practice login coverage");
  await page.getByLabel("Project description").fill("Secure browser login acceptance");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.getByLabel("Journey name").fill("Practice login journey");
  await page.getByLabel("Target URL").fill("https://practicetestautomation.com/practice-test-login/");
  await page.getByLabel("Objective").fill('Log in and validate "Logged In Successfully"');
  await page.getByRole("button", { name: "Review journey" }).click();
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password", { exact: true }).fill(password!);
  await page.getByRole("button", { name: "Review journey" }).click();
  await expect(page.getByText(/••••••••/)).toBeVisible();
  await page.getByRole("button", { name: "Generate and save" }).click();
  await expect(page.getByRole("heading", { name: "Script ready" })).toBeVisible();

  const journeys = (await (await request.get(`${apiBase}/api/journeys`)).json()).data;
  const journey = journeys.find((item: { name: string }) => item.name === "Practice login journey");
  expect(journey.has_credentials).toBe(true);
  expect(journey.script).not.toContain(username);
  expect(journey.script).not.toContain(password);
  const run = (await (await request.post(`${apiBase}/api/journeys/${journey.id}/run`)).json()).data;
  expect(["PASSED", "PASSED_AFTER_REPAIR"]).toContain(run.status);
  const detail = (await (await request.get(`${apiBase}/api/runs/${run.id}`)).json()).data;
  expect(detail.script_snapshot).toContain("sync_playwright");
  expect(detail.attempts).toHaveLength(1);
  expect(detail.artifacts.some((item: { kind: string }) => item.kind === "screenshot")).toBe(true);
  expect(detail.artifacts.some((item: { kind: string }) => item.kind === "video")).toBe(true);
  expect(JSON.stringify(detail)).not.toContain(password);
});
