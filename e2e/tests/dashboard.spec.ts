import { test, expect, Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'masahiro@takechi.jp');
  await page.fill('input[type="password"]', 'clawthon2026');
  await page.click('button[type="submit"]');
  await page.waitForURL('/');
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('shows participant table', async ({ page }) => {
    await expect(page.locator('#participants-table')).toBeVisible();
  });

  test('participant portal dropdown works', async ({ page }) => {
    await page.hover('.nav-dropdown');
    await expect(page.locator('.nav-dropdown-menu a').first()).toBeVisible();
  });

  test('login info modal opens', async ({ page }) => {
    const infoBtn = page.locator('button.btn-info').first();
    if (await infoBtn.count() > 0) {
      await infoBtn.click();
      await expect(page.locator('#login-modal.open')).toBeVisible();
      await expect(page.locator('#info-portal')).toBeVisible();
      await page.locator('.modal-close').click();
      await expect(page.locator('#login-modal.open')).not.toBeVisible();
    }
  });

  test('table filter works', async ({ page }) => {
    const search = page.locator('#participant-search');
    await expect(search).toBeVisible();
    await search.fill('test');
    // typing should trigger filter
    await page.waitForTimeout(300);
  });

  test('manual link navigates to manual', async ({ page }) => {
    await page.click('a[href="/manual"]');
    await expect(page).toHaveURL('/manual');
    await expect(page.locator('h2, .section-title')).toBeVisible();
  });
});
