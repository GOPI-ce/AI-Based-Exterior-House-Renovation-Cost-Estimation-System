import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const fixture = (name: string) => path.join(__dirname, "fixtures", name);

async function openDemo(page: Page) {
  await page.goto("/p/demo");
  await expect(page.getByText("estimated total")).toBeVisible();
}

/** Click a point of the photo given in the photo's own pixel coordinates (demo photo: 1280 x 960). */
async function clickPhoto(page: Page, x: number, y: number) {
  const box = (await page.locator("svg.touch-none").first().boundingBox())!;
  await page.mouse.click(box.x + (x / 1280) * box.width, box.y + (y / 960) * box.height);
}

test("home page offers upload and demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /See your house renovated/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Upload a house photo" })).toBeVisible();
});

test("an unusable photo is rejected with guidance", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles(fixture("blurry-house.jpg"));
  await expect(page.getByText("This photo can't be used")).toBeVisible();
  await expect(page.getByText(/too blurry|slightly soft/)).toBeVisible();
});

test("demo: switching designs changes the estimate", async ({ page }) => {
  await openDemo(page);
  const total = page.locator("text=estimated total").locator("..").locator("p").nth(1);
  await page.getByRole("button", { name: "Budget repaint", exact: true }).first().click();
  const budget = await total.textContent();
  await page.getByRole("button", { name: "Luxury granite & HPL", exact: true }).first().click();
  await expect(total).not.toHaveText(budget!);
});

test("demo: choose a material and a shade for a surface", async ({ page }) => {
  await openDemo(page);
  await clickPhoto(page, 1120, 600); // side wall
  await expect(page.getByText("Side elevation wall")).toBeVisible();
  await page.getByRole("button", { name: /Dulux/ }).first().click();
  await page.getByPlaceholder(/Search \d+ shades/).fill("sage");
  await page.getByRole("button", { name: "Sage Green" }).click();
  await expect(page.getByText("Shade:").locator("..")).toContainText("Sage Green");
});

test("surfaces: drag a corner, then undo", async ({ page }) => {
  await openDemo(page);
  await page.getByRole("button", { name: /Surfaces/ }).first().click();
  await clickPhoto(page, 1120, 600);
  const handle = page.locator('circle[data-kind="vertex"]').first();
  const before = (await handle.boundingBox())!;
  await page.mouse.move(before.x + before.width / 2, before.y + before.height / 2);
  await page.mouse.down();
  await page.mouse.move(before.x + 40, before.y + 30, { steps: 6 });
  await page.mouse.up();
  expect(Math.abs((await handle.boundingBox())!.x - before.x)).toBeGreaterThan(20);
  await page.keyboard.press("Control+z");
  expect(Math.abs((await handle.boundingBox())!.x - before.x)).toBeLessThan(2);
});

test("scale: planes show confidence and accept a new reference", async ({ page }) => {
  await openDemo(page);
  await page.getByRole("button", { name: /Scale/ }).first().click();
  await expect(page.getByText("High · 90%").first()).toBeVisible();
  const refs = page.locator('input[aria-label="Reference name"]');
  const count = await refs.count();
  await page.getByRole("button", { name: "Add reference" }).first().click();
  const box = (await page.locator("svg.touch-none").first().boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.1, box.y + box.height * 0.4);
  await page.mouse.click(box.x + box.width * 0.1, box.y + box.height * 0.6);
  await expect(refs).toHaveCount(count + 1);
});

test("depth: surfaces are measured at their own distance", async ({ page }) => {
  await openDemo(page);
  await page.getByRole("button", { name: /Surfaces/ }).first().click();
  await clickPhoto(page, 1120, 600); // side wall, set back behind the house front
  await expect(page.getByText(/About 2\d\.\d m/)).toBeVisible();
  await page.getByRole("button", { name: /Scale/ }).first().click();
  await expect(page.getByText("Distance-aware.")).toBeVisible();
  await expect(page.getByText(/corrected for distance by the depth map/)).toBeVisible();
});

test("estimate: range, site items, city and BOQ export", async ({ page }) => {
  await openDemo(page);
  await page.getByRole("button", { name: /Estimate/ }).first().click();
  await expect(page.getByText("Most likely total (incl. GST)")).toBeVisible();
  await expect(page.getByText(/Likely range/).first()).toBeVisible();
  await expect(page.getByText("Scaffolding / staging (MS, ~1 month)").first()).toBeVisible();

  const total = page.getByText("Most likely total").locator("xpath=following-sibling::*[1]").first();
  const ahmedabad = await total.textContent();
  await page.getByLabel("City (adjusts labour and material rates)").selectOption("mumbai");
  await expect(total).not.toHaveText(ahmedabad!);

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "BOQ (CSV)" }).click()]);
  const csv = fs.readFileSync((await download.path())!, "utf-8");
  expect(csv).toContain("Bill of quantities");
  expect(csv).toContain("Most likely total");
});

test("report: PDF downloads", async ({ page }) => {
  await openDemo(page);
  await page.getByRole("button", { name: /Report/ }).first().click();
  const [download] = await Promise.all([page.waitForEvent("download", { timeout: 60_000 }), page.getByRole("button", { name: "Download PDF report" }).click()]);
  expect(fs.readFileSync((await download.path())!).subarray(0, 5).toString()).toBe("%PDF-");
});

// Next keeps left pages alive for instant Back navigation, so loading states must not survive a page change.
test("returning home after creating a project shows a ready upload button", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles(fixture("house.jpg"));
  await page.waitForURL(/\/p\/[a-f0-9]+/);
  await page.getByRole("link").first().click(); // the logo
  await page.waitForURL((url) => url.pathname === "/");
  await expect(page.getByRole("button", { name: "Upload a house photo" })).toBeEnabled();
  await expect(page.getByText("Creating project…")).toHaveCount(0);
});

test("going back after making a copy shows a ready copy button", async ({ page }) => {
  await openDemo(page);
  await page.getByRole("button", { name: "Make my copy" }).click();
  await page.waitForURL((url) => /\/p\/[a-f0-9]+$/.test(url.pathname) && !url.pathname.endsWith("/demo"));
  await page.goBack();
  await expect(page.getByRole("button", { name: "Make my copy" })).toBeEnabled();
});

test("upload a real photo and run the AI pipeline", async ({ page }) => {
  test.skip(!process.env.E2E_AI, "Set E2E_AI=1 to run against live Gemini + SAM (uses API quota)");
  test.setTimeout(240_000);
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles(fixture("house.jpg"));
  await page.waitForURL(/\/p\/[a-f0-9]+/);
  await expect(page.getByText(/Found \d+ building parts/)).toBeVisible({ timeout: 180_000 });
  await page.getByRole("button", { name: /Scale/ }).first().click();
  await expect(page.getByText(/High|Medium|Low ·/).first()).toBeVisible();
  await expect(page.getByText("Distance-aware.")).toBeVisible();
});

test("AI designer creates a design within the budget", async ({ page }) => {
  test.skip(!process.env.E2E_AI, "Set E2E_AI=1 to run against live Gemini (uses API quota)");
  test.setTimeout(180_000);
  await openDemo(page);
  await page.getByRole("button", { name: "Make my copy" }).click();
  await page.waitForURL((url) => /\/p\/[a-f0-9]+$/.test(url.pathname) && !url.pathname.endsWith("/demo"));
  await page.getByRole("button", { name: /Design it for my budget/ }).click();
  await page.getByLabel("Budget").fill("350000");
  await page.getByRole("button", { name: "Warm with natural stone" }).click();
  await page.getByRole("button", { name: "Create AI design" }).click();
  await expect(page.getByText("within budget", { exact: true }).first()).toBeVisible({ timeout: 150_000 });
  await expect(page.getByText(/Added as a new design tab/).first()).toBeVisible();
});
