const { test, expect } = require("@playwright/test");

test.describe.configure({ mode: "serial" });

test("owner enrolls MFA and receives recovery codes once", async ({ page }) => {
  await page.goto("/admin/");
  await page.getByLabel("账户").fill("ninesense");
  await page.getByLabel("密码").fill("E2E-secure-password-2026");
  await page.getByRole("button", { name: "继续" }).click();

  await expect(page.getByRole("heading", { name: "设置两步验证" })).toBeVisible();
  await expect(page.locator("canvas[aria-label='两步验证二维码']")).toBeVisible();
  const codeResponse = await page.request.get("/__e2e/current-totp");
  expect(codeResponse.status()).toBe(200);
  const code = await codeResponse.json();
  await page.getByLabel("动态验证码").fill(code.value);
  await page.getByRole("button", { name: "启用并登录" }).click();

  await expect(page.getByRole("heading", { name: "保存恢复码" })).toBeVisible();
  await expect(page.getByTestId("recovery-code")).toHaveCount(10);
  await page.getByRole("button", { name: "我已保存，进入后台" }).click();

  await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();
  for (const label of ["总览", "互动", "内容", "页面", "媒体", "发布", "统计", "运维", "设置与安全"]) {
    await expect(page.getByRole("link", { name: label, exact: true })).toBeVisible();
  }
  await expect(page.getByText("待处理互动")).toBeVisible();

  await page.getByRole("link", { name: "通知", exact: true }).click();
  await expect(page.getByRole("heading", { name: "通知中心" })).toBeVisible();
  await page.getByRole("link", { name: "设置与安全", exact: true }).click();
  await expect(page.getByRole("heading", { name: "设置与安全" })).toBeVisible();
  await expect(page.getByText("当前会话")).toBeVisible();

  const reauthCode = await page.request.get("/__e2e/current-totp").then(response => response.json());
  await page.getByLabel("密码").fill("incorrect-password");
  await page.getByLabel("动态验证码或恢复码").fill(reauthCode.value);
  const failedReauthentication = page.waitForResponse(response => (
    response.url().endsWith("/api/admin/session/reauthenticate")
    && response.request().method() === "POST"
  ));
  await page.getByRole("button", { name: "重新验证身份" }).click();
  expect((await failedReauthentication).status()).toBe(401);
  await page.evaluate(() => new Promise(resolve => (
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  )));
  await expect(page.getByRole("heading", { name: "设置与安全" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "登录管理平台" })).toHaveCount(0);

  const challengeResponse = await page.request.post("/api/admin/session", {
    data: { username: "ninesense", password: "E2E-secure-password-2026" }
  });
  const challenge = await challengeResponse.json();
  const secondCode = await page.request.get("/__e2e/current-totp").then(response => response.json());
  const secondLogin = await page.request.post("/api/admin/session/mfa", {
    data: { challenge_token: challenge.challenge_token, code: secondCode.value }
  });
  expect(secondLogin.status()).toBe(200);
  await page.reload();
  await page.getByRole("link", { name: "设置与安全", exact: true }).click();
  await expect(page.getByRole("button", { name: "撤销" })).toHaveCount(1);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "撤销" }).click();
  await expect(page.getByRole("button", { name: "撤销" })).toHaveCount(0);

  await page.getByRole("link", { name: "内容", exact: true }).click();
  await expect(page.getByText("内容将在后续阶段启用")).toBeVisible();

  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/admin/");
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `admin overflows at ${viewport.width}px`).toBeLessThanOrEqual(1);
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/admin/");
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("heading", { name: "登录管理平台" })).toBeVisible();
});
