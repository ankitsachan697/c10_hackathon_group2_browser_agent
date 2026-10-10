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
  await page.getByRole("button", { name: "Run now" }).click();
  await expect(page.getByText("Started Checkout coverage")).toBeVisible();

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
  await page.getByRole("button", { name: "Delete" }).click();
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
