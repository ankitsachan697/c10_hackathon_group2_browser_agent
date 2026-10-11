import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname;
    const fixtures: Record<string, unknown> = {
      "/api/projects": [{ id: "project-ui", name: "Project workspace", description: "Saved login coverage" }],
      "/api/journeys": [
        { id: "journey-ui", project_id: "project-ui", name: "Login journey", target_url: "https://app.example/login", script: "print('saved')", active: 1 },
        { id: "journey-other", project_id: "project-other", name: "Unrelated journey", target_url: "https://other.example", script: "print('other')", active: 1 },
      ],
      "/api/runs": [{ id: "run-ui", project_id: "project-ui", journey_id: "journey-ui", created_at: "2026-10-11T10:00:00Z", status: "PASSED", attempt_count: 1, script_version: 3, trigger_source: "ON_DEMAND" }],
      "/api/runs/run-ui/rerun": { id: "run-rerun", project_id: "project-ui", journey_id: "journey-ui", created_at: "2026-10-11T11:00:00Z", status: "PASSED", attempt_count: 1, script_version: 3, trigger_source: "RERUN_SNAPSHOT" },
      "/api/journeys/journey-ui/run": { id: "run-current", project_id: "project-ui", journey_id: "journey-ui", created_at: "2026-10-11T11:00:00Z", status: "PASSED", attempt_count: 1, script_version: 3, trigger_source: "ON_DEMAND" },
    };
    return route.fulfill({ json: { data: fixtures[path] ?? {}, error: null, meta: {} } });
  });
});

test("project menu is fully clickable outside the table clipping boundary", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: "Project actions" }).click();
  const menu = page.getByRole("menu");
  await expect(menu.getByRole("menuitem", { name: "Delete", exact: true })).toBeVisible();
  expect(await menu.evaluate(element => {
    const box = element.getBoundingClientRect();
    return !element.closest(".table-wrap") && element.contains(document.elementFromPoint(box.left + 12, box.bottom - 12));
  })).toBe(true);
  await page.getByRole("menuitem", { name: "View run history" }).click();
  const drawer = page.getByRole("dialog", { name: "Project workspace" });
  await expect(drawer.getByRole("tab", { name: /Run history/ })).toHaveAttribute("aria-selected", "true");
  await expect(drawer.getByRole("link", { name: "Open run run-ui", exact: true })).toBeVisible();
  const request = page.waitForRequest("**/api/runs/run-ui/rerun");
  await drawer.getByRole("button", { name: "Rerun this version" }).click();
  expect((await request).postDataJSON()).toEqual({ mode: "snapshot" });
  await expect(drawer.getByRole("link", { name: "Open latest run" })).toHaveAttribute("href", "/runs/run-rerun");
});

test("project row opens saved journeys and its drawer fits mobile without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/projects");
  await page.getByRole("button", { name: "Project actions" }).click();
  const menu = page.getByRole("menu");
  expect(await menu.evaluate(element => {
    const box = element.getBoundingClientRect();
    return box.left >= 0 && box.right <= window.innerWidth && box.top >= 0 && box.bottom <= window.innerHeight;
  })).toBe(true);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Open project Project workspace" }).click();
  const drawer = page.getByRole("dialog", { name: "Project workspace" });
  await expect(drawer.getByRole("heading", { name: "Login journey" })).toBeVisible();
  await expect(drawer.getByText("Unrelated journey")).toHaveCount(0);
  expect(await drawer.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await drawer.getByRole("button", { name: "Run saved script" }).click();
  await expect(drawer.getByRole("link", { name: "Open latest run" })).toHaveAttribute("href", "/runs/run-current");
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Open project Project workspace" })).toBeFocused();
});
