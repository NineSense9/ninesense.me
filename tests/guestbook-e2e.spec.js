const { test, expect } = require("@playwright/test");

test("public moderation, private handling, and responsive layouts", async ({ page }) => {
  const pageErrors = [];
  const failedAssets = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("response", response => {
    if (["document", "stylesheet", "script", "image", "font"].includes(response.request().resourceType()) && response.status() >= 400) {
      failedAssets.push(`${response.status()} ${response.url()}`);
    }
  });

  const publicText = "这是一条来自浏览器验收的公开留言";
  const privateText = "这是一条只能在后台看到的浏览器私信";
  const ownerReply = "谢谢你认真走完了这次测试。";

  await page.goto("/guestbook/");
  await expect(page.getByRole("heading", { name: "LEAVE A NOTE FOR LATER" })).toBeVisible();
  await expect(page.locator(".page-intro > div:first-child > .eyebrow"))
    .toHaveText("NINESENSE / GUESTBOOK / PRIVATE LETTERS");
  const blurTitle = page.locator("[data-blur-title]");
  const blurWords = blurTitle.locator(".blur-word");
  await expect(blurWords).toHaveCount(5);
  await expect(blurWords).toHaveText(["LEAVE", "A", "NOTE", "FOR", "LATER"]);
  await expect(blurTitle).toHaveClass(/is-active/);

  await page.waitForTimeout(2200);
  await expect(blurTitle).toHaveClass(/is-settled/);
  await expect(blurTitle).not.toHaveClass(/is-active/);
  await expect(blurWords.first()).toHaveCSS("opacity", "1");
  await expect(blurWords.first()).toHaveCSS("filter", "none");
  await expect(blurWords.first()).toHaveCSS("transform", "none");

  const titleLines = blurTitle.locator("[data-blur-text]");
  const firstTitleLine = await titleLines.nth(0).boundingBox();
  const secondTitleLine = await titleLines.nth(1).boundingBox();
  expect(firstTitleLine).not.toBeNull();
  expect(secondTitleLine).not.toBeNull();
  expect(secondTitleLine.y).toBeGreaterThanOrEqual(firstTitleLine.y + firstTitleLine.height - 1);
  await page.locator("#nickname").fill("验收访客");
  await page.locator("#contact").fill("visitor@example.com");
  await page.locator("#content").fill(publicText);
  await page.getByRole("button", { name: "发送这段话" }).click();
  await expect(page.locator("#form-status")).toContainText("审核后出现");

  await page.goto("/admin/");
  await page.locator("#username").fill("ninesense");
  await page.locator("#password").fill("E2E-secure-password-2026");
  await page.getByRole("button", { name: "进入后台" }).click();
  await expect(page.locator("#dashboard")).toBeVisible();
  await page.locator(".inbox-item").filter({ hasText: publicText }).click();
  await expect(page.locator("#contact-value")).toHaveText("visitor@example.com");
  await expect(page.locator("#reply-editor")).toBeVisible();
  await page.locator("#reply-text").fill(ownerReply);
  await page.getByRole("button", { name: "通过并回复" }).click();
  await expect(page.locator("#detail-status")).toHaveText("PUBLISHED");

  await page.goto("/guestbook/");
  await expect(page.getByText(publicText)).toBeVisible();
  await expect(page.getByText(ownerReply)).toBeVisible();
  await page.waitForTimeout(2100);
  await page.getByLabel("私信给我").check();
  await page.locator("#nickname").fill("私信访客");
  await page.locator("#contact").fill("13800138000");
  await page.locator("#content").fill(privateText);
  await page.getByRole("button", { name: "发送这段话" }).click();
  await expect(page.locator("#form-status")).toContainText("只会在后台显示");
  await expect(page.getByText(privateText)).toHaveCount(0);

  await page.goto("/admin/");
  await expect(page.locator("#dashboard")).toBeVisible();
  await page.locator(".inbox-item").filter({ hasText: privateText }).click();
  await expect(page.locator("#contact-value")).toHaveText("13800138000");
  await page.getByRole("button", { name: "标记已处理" }).click();
  await expect(page.locator("#detail-status")).toHaveText("HANDLED");

  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport);
    for (const path of ["/", "/guestbook/", "/admin/"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      if (path === "/guestbook/") await page.waitForTimeout(1600);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${path} overflows at ${viewport.width}px`).toBeLessThanOrEqual(1);
    }
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/guestbook/");
  const onceTitle = page.locator("[data-blur-title]");
  await page.waitForTimeout(1600);
  await expect(onceTitle).toHaveClass(/is-settled/);
  await page.mouse.move(1400, 980);
  await onceTitle.hover();
  await page.waitForTimeout(300);
  await expect(onceTitle).toHaveClass(/is-settled/);
  await expect(onceTitle).not.toHaveClass(/is-active/);

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(page.locator("[data-blur-title] .blur-word")).toHaveCount(0);
  await expect(page.locator("[data-blur-text]").nth(0)).toHaveText("LEAVE A NOTE");
  await expect(page.locator("[data-blur-text]").nth(1)).toHaveText("FOR LATER");
  await page.emulateMedia({ reducedMotion: "no-preference" });

  await page.goto("/guestbook/");
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement !== document.body)).toBeTruthy();
  expect(pageErrors).toEqual([]);
  expect(failedAssets).toEqual([]);
});
