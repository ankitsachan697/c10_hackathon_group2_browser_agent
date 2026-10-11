import { expect, test } from '@playwright/test';

test('Studio lab controls a target and starts an explicitly configured journey', async ({ page }) => {
  await page.goto('/demo-lab');
  await expect(page.getByText('Group2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'New scenario' }).click();
  await expect(page.getByLabel('Target URL')).not.toHaveValue('');
  await page.getByLabel('Change checkout locator').check();
  await expect(page.getByRole('status')).toContainText('Target updated');
  const target = await page.getByLabel('Target URL').inputValue();
  const shop = await page.context().newPage();
  await shop.goto(target);
  await shop.getByLabel('Username / email', { exact: true }).fill('demo@example.test');
  await shop.getByLabel('Password', { exact: true }).fill('DemoPass123!');
  await shop.getByRole('button', { name: 'Sign in', exact: true }).click();
  await shop.getByRole('button', { name: 'Add Studio Notebook to cart' }).click();
  await shop.getByRole('button', { name: 'View cart', exact: true }).click();
  await expect(shop.getByRole('button', { name: 'Continue to shipping' })).toBeVisible();
  await shop.close();
  await page.getByRole('button', { name: 'Reset target' }).click();
  await expect(page.getByLabel('Change checkout locator')).not.toBeChecked();
  await page.getByRole('link', { name: 'Create demo journey' }).click();
  await expect(page.getByLabel('Journey name')).toHaveValue('Demo shop checkout');
  await expect(page.getByLabel('Target URL')).toHaveValue(target);
  await expect(page.getByLabel('Username', { exact: true })).toHaveValue('demo@example.test');
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('');
  await expect(page.getByRole('tab', { name: 'Playwright Script' })).toHaveCount(0);
});
