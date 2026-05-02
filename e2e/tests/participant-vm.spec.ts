import { test, expect } from '@playwright/test';

test.describe('Participant VMs', () => {
  test('p01 is accessible', async ({ page }) => {
    await page.goto('https://p01.iseai.neuratools.ai/');
    await expect(page.locator('header')).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveTitle(/Clawthon/);
  });

  test('p01 VSCode is accessible', async ({ page }) => {
    const res = await page.request.get('https://p01.iseai.neuratools.ai/code/');
    expect(res.status()).toBeLessThan(400);
  });

  test('p01 OpenHands is accessible', async ({ page }) => {
    const res = await page.request.get('https://p01.iseai.neuratools.ai/openhands/');
    expect(res.status()).toBeLessThan(400);
  });
});
