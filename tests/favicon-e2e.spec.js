const { test, expect } = require("@playwright/test");

test("每个站点入口都使用 NineSense 头像作为标签页图标", async ({ page }) => {
  for (const path of ["/", "/guestbook/", "/records/", "/records/study/", "/admin/"]) {
    await page.goto(path);
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", "/assets/avatar-qq.jpg");
  }
});
