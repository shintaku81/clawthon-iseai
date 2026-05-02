import { test, expect, Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'masahiro@takechi.jp');
  await page.fill('input[type="password"]', 'clawthon2026');
  await page.click('button[type="submit"]');
  await page.waitForURL('/');
}

test.describe('VM Status', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('participant row shows VM status badge', async ({ page }) => {
    const rows = page.locator('#participants-tbody tr');
    const count = await rows.count();
    if (count > 0) {
      const badge = rows.first().locator('.badge');
      await expect(badge).toBeVisible();
      const text = await badge.textContent();
      expect(['RUNNING', 'TERMINATED', 'NOT_EXISTS']).toContain(text?.trim());
    }
  });

  test('running VM shows access links', async ({ page }) => {
    const runningRow = page.locator('#participants-tbody tr').filter({ hasText: 'RUNNING' });
    if (await runningRow.count() > 0) {
      await expect(runningRow.first().locator('.link-btn')).toBeVisible();
    }
  });
});
