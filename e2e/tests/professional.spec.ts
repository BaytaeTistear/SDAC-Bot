import { expect, test } from '@playwright/test';

test('public API, status, and documentation are available', async ({ page, request }) => {
  await page.goto('/api/docs');
  await expect(page.getByRole('heading', { name: 'Sana-Chan Public API' })).toBeVisible();
  const status = await request.get('/status?format=json');
  expect(status.ok()).toBeTruthy();
  expect((await status.json()).status).toMatch(/operational|degraded/);
  const spec = await request.get('/api/v1/openapi.json');
  expect((await spec.json()).openapi).toBe('3.1.0');
});

test('mobile public pages avoid horizontal document overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/status');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBeFalsy();
});
