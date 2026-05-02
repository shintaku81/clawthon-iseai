import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('login page shows form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('invalid login shows error', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'wrong@example.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    await expect(page.locator('.error, [class*="error"], [class*="alert"]')).toBeVisible({ timeout: 5000 });
  });

  test('valid login redirects to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"]', 'masahiro@takechi.jp');
    await page.fill('input[type="password"]', 'clawthon2026');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/', { timeout: 10000 });
    await expect(page.locator('header')).toBeVisible();
  });
});
