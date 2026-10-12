const { test, expect } = require('@playwright/test');

for (const width of [1440, 768, 390, 320]) {
  test(`homepage project layout and competition navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    await page.goto('/');
    const cards = page.locator('.project-card');
    await expect(cards).toHaveCount(2);
    const first = await cards.nth(0).boundingBox();
    const second = await cards.nth(1).boundingBox();
    if (width > 700) expect(Math.abs(first.y - second.y)).toBeLessThan(2);
    else expect(second.y).toBeGreaterThan(first.y + first.height);
    const ops = await page.locator('.ops-case').boundingBox();
    expect(ops.y).toBeGreaterThan(second.y + second.height);
    await expect(page.locator('#competitions img')).toHaveCount(4);
    for (const role of ['KIMI K3', 'ChatGPT', 'grok4.6 / grok4.7']) await expect(page.locator('.collab-strip')).toContainText(role);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await cards.nth(0).click();
    await expect(page).toHaveURL(/\/projects\/veriflow\/$/);
    await page.getByRole('link', { name: 'GhostQA ↗', exact: true }).click();
    await expect(page).toHaveURL(/\/projects\/ghostqa\/$/);
    await page.getByRole('link', { name: '返回项目', exact: true }).click();
    await expect(page).toHaveURL(/\/#work$/);
    if (width <= 820) {
      await page.getByRole('button', { name: '打开导航菜单' }).click();
      await page.locator('.mobile-menu-item[href="#competitions"]').click();
    } else await page.getByRole('link', { name: '竞赛', exact: true }).click();
    await expect(page).toHaveURL(/\/#competitions$/);
  });

  for (const name of ['veriflow', 'ghostqa']) {
    test(`${name} images and viewer at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 950 });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const response = await page.goto(`/projects/${name}/`);
      expect(response.status()).toBe(200);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(name === 'veriflow' ? 'VeriFlow' : 'GhostQA');
      const shots = page.locator('.shot-open');
      await expect(shots).toHaveCount(3);
      for (let i = 0; i < 3; i++) {
        const shot = shots.nth(i);
        await shot.scrollIntoViewIfNeeded();
        const image = shot.locator('img');
        await expect(image).toHaveJSProperty('complete', true);
        expect(await image.evaluate(n => n.naturalWidth)).toBeGreaterThan(500);
        expect(await image.evaluate(n => n.naturalHeight)).toBeGreaterThan(200);
        expect(await image.evaluate(n => n.naturalWidth === Number(n.getAttribute('width')) && n.naturalHeight === Number(n.getAttribute('height')))).toBe(true);
        await shot.click();
        const dialog = page.locator('#image-viewer');
        await expect(dialog).toBeVisible();
        await expect(dialog.locator('img')).toHaveJSProperty('complete', true);
        await expect(dialog.locator('#viewer-caption')).toContainText('本地演示环境');
        if (width <= 560) expect(await dialog.locator('.viewer-media').evaluate(n => n.scrollWidth > n.clientWidth)).toBe(true);
        if (i === 0) await page.keyboard.press('Escape');
        else if (i === 1) await dialog.getByRole('button', { name: '关闭 ×' }).click();
        else await page.mouse.click(1, 1);
        await expect(dialog).not.toBeVisible();
        await expect(shot).toBeFocused();
        expect(await page.locator('html').getAttribute('class')).not.toContain('image-viewer-open');
      }
      expect(errors).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  }
}

for (const width of [390, 320]) {
  test(`short phone menu remains scrollable and all links work at ${width}x568`, async ({ page }) => {
    await page.setViewportSize({ width, height: 568 });
    await page.goto('/');
    const toggle = page.locator('.mobile-menu-toggle');
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await page.locator('.mobile-menu-item[href="#competitions"]').click();
    await expect(page).toHaveURL(/\/#competitions$/);
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.click();
    const panel = page.locator('#mobile-menu-panel');
    await panel.hover({ position: { x: 100, y: 300 } });
    await page.mouse.wheel(0, 900);
    await expect.poll(() => panel.evaluate(n => n.scrollTop)).toBeGreaterThan(0);
    const guestbook = page.locator('.mobile-menu-item[href="./guestbook/"]');
    await expect(guestbook).toBeInViewport({ ratio: 1 });
    await page.keyboard.press('Escape');
    await toggle.click();
    expect(await panel.evaluate(n => n.scrollTop)).toBe(0);
    await expect(page.locator('.mobile-menu-item[href="#top"]')).toBeFocused();
    for (let i = 0; i < 7; i++) await page.keyboard.press('Tab');
    await expect(guestbook).toBeFocused();
    await expect(guestbook).toBeInViewport({ ratio: 1 });
    await guestbook.click();
    await expect(page).toHaveURL(/\/guestbook\/$/);
  });
}
