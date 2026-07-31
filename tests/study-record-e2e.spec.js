const { test, expect } = require("@playwright/test");


test.describe.configure({ mode: "serial" });


async function loginOwner(page) {
  await page.goto("/admin/");
  await page.getByLabel("账户").fill("ninesense");
  await page.getByLabel("密码").fill("E2E-secure-password-2026");
  await page.getByRole("button", { name: "继续", exact: true }).click();

  await expect(page.getByLabel("动态验证码")).toBeVisible();
  const codeResponse = await page.request.get("/__e2e/current-totp");
  expect(codeResponse.status()).toBe(200);
  const { value } = await codeResponse.json();
  expect(value).toMatch(/^\d{6}$/);
  await page.getByLabel("动态验证码").fill(value);
  await page.locator("form.auth-card button[type='submit']").click();

  const recoveryHeading = page.getByRole("heading", { name: "保存恢复码", exact: true });
  await expect(page.getByRole("heading", { name: /保存恢复码|总览/ })).toBeVisible();
  if (await recoveryHeading.count()) {
    await expect(recoveryHeading).toBeVisible();
    await page.getByRole("button", { name: "我已保存，进入后台", exact: true }).click();
  }
  await expect(page.getByRole("heading", { name: "总览", exact: true })).toBeVisible();
}


test("owner records study progress and public page stays read only", async ({ page }) => {
  await loginOwner(page);
  await page.getByRole("link", { name: "学习管理", exact: true }).click();
  await expect(page.getByRole("heading", { name: "今天", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "新增任务", exact: true }).click();
  const newTask = page.locator("form.new-study-task");
  await newTask.getByLabel("标题").fill("数据结构复盘");
  await newTask.getByLabel("具体内容").fill("图论与最短路");
  await newTask.getByRole("button", { name: "新增任务", exact: true }).click();
  await expect(page.locator('input[value="数据结构复盘"]')).toBeVisible();

  await page.getByRole("button", { name: "408", exact: true }).click();
  await page.getByRole("button", { name: "25 / 5", exact: true }).click();
  await page.getByRole("button", { name: "开始专注", exact: true }).click();
  await expect(page.getByText("正在专注 408", { exact: true })).toBeVisible();

  await page.goto("/records/study/");
  await expect(page.getByRole("heading", { name: "备考这件事 一天一天记录" })).toBeVisible();
  await expect(page.getByText("正在专注 408", { exact: true })).toBeVisible();
  await expect(page.locator("#study-today").getByText("数据结构复盘", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /新增|修改|删除|开始专注/ })).toHaveCount(0);

  await page.goto("/admin/study");
  await page.getByRole("button", { name: "放弃本次", exact: true }).click();
  await expect(page.getByRole("button", { name: "开始专注", exact: true })).toBeVisible();
});


test("study pages fit desktop tablet and phone widths", async ({ page }) => {
  await loginOwner(page);
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
    { width: 320, height: 800 }
  ]) {
    await page.setViewportSize(viewport);
    for (const path of ["/records/study/", "/admin/study", "/admin/study/schedule", "/admin/study/history", "/admin/study/focus", "/admin/study/exams"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${path} overflows at ${viewport.width}px`).toBeLessThanOrEqual(1);
    }
  }
});
