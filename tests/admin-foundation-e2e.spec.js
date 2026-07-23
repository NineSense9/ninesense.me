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
});
