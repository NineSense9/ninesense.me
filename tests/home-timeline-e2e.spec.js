const { test, expect } = require("@playwright/test");


test("desktop timeline provides accessible paging controls", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/#timeline");

  const timeline = page.locator(".timeline-shell");
  const previous = page.getByRole("button", { name: "向左查看时间线" });
  const next = page.getByRole("button", { name: "向右查看时间线" });

  await expect(previous).toBeVisible();
  await expect(next).toBeVisible();
  await expect(previous).toBeDisabled();

  const start = await timeline.evaluate(node => node.scrollLeft);
  await next.click();
  await expect.poll(() => timeline.evaluate(node => node.scrollLeft)).toBeGreaterThan(start + 300);
  await expect(previous).toBeEnabled();

  await timeline.evaluate(node => node.scrollTo({ left: 0, behavior: "auto" }));
  await expect(previous).toBeDisabled();
  const nextBox = await next.boundingBox();
  expect(nextBox).not.toBeNull();
  await page.mouse.move(nextBox.x + nextBox.width / 2, nextBox.y + nextBox.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(1000);
  await page.mouse.up();
  const heldDistance = await timeline.evaluate(node => node.scrollLeft);
  expect(heldDistance).toBeGreaterThan(30);
  expect(heldDistance).toBeLessThan(300);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(previous).toBeHidden();
  await expect(next).toBeHidden();
});
