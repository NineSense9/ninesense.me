const { test, expect } = require("@playwright/test");


async function currentTotp(page) {
  await expect.poll(async () => {
    const response = await page.request.get("/__e2e/current-totp");
    return (await response.json()).value;
  }).toMatch(/^\d{6}$/);
  return page.request.get("/__e2e/current-totp").then(response => response.json()).then(body => body.value);
}


async function loginAdmin(page) {
  await page.goto("/admin/");
  if (await page.getByLabel("账户").isVisible().catch(() => false)) {
    await page.getByLabel("账户").fill("ninesense");
    await page.getByLabel("密码").fill("E2E-secure-password-2026");
    await page.getByRole("button", { name: "继续" }).click();
    await page.getByLabel("动态验证码").fill(await currentTotp(page));
    const setupButton = page.getByRole("button", { name: "启用并登录" });
    if (await setupButton.isVisible().catch(() => false)) {
      await setupButton.click();
      await page.getByRole("button", { name: "我已保存，进入后台" }).click();
    } else {
      await page.getByRole("button", { name: "验证并登录" }).click();
    }
  }
  await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();
  await page.getByRole("link", { name: "互动", exact: true }).click();
  await expect(page.getByRole("heading", { name: "互动中心" })).toBeVisible();
}

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

  await loginAdmin(page);
  await page.getByRole("button", { name: new RegExp(publicText) }).click();
  await page.getByRole("button", { name: "查看联系方式" }).click();
  await expect(page.getByRole("heading", { name: "重新验证后查看" })).toBeVisible();
  await page.getByLabel("验证密码").fill("E2E-secure-password-2026");
  await page.getByLabel("验证动态码").fill(await currentTotp(page));
  await page.getByRole("button", { name: "验证并查看" }).click();
  await expect(page.getByText("visitor@example.com")).toBeVisible();
  await page.getByLabel("公开回复").fill(ownerReply);
  await page.getByRole("button", { name: "通过并回复" }).click();
  await expect(page.getByLabel("互动详情").getByText("已公开", { exact: true })).toBeVisible();

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

  await page.goto("/admin/inbox");
  await expect(page.getByRole("heading", { name: "互动中心" })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(privateText) }).click();
  await page.getByRole("button", { name: "标记已处理" }).click();
  await expect(page.getByLabel("互动详情").getByText("已处理", { exact: true })).toBeVisible();

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
