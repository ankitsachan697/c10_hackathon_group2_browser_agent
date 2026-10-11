import { expect, test } from "@playwright/test";

async function setup(page: import("@playwright/test").Page) {
  const response = await page.request.post('/api/demo-lab/scenarios', { data: {} });
  expect(response.status()).toBe(201);
  const { data } = await response.json();
  await page.goto(data.target_path);
  return data;
}
async function login(page: import("@playwright/test").Page, password = 'DemoPass123!') {
  await page.getByLabel('Username / email', { exact: true }).fill('demo@example.test');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
}
async function checkout(page: import("@playwright/test").Page) {
  await page.getByRole('button', { name: 'Add Studio Notebook to cart', exact: true }).click();
  await page.getByRole('button', { name: 'View cart', exact: true }).click();
  await page.getByRole('button', { name: 'Checkout', exact: true }).click();
  await page.getByLabel('Full name', { exact: true }).fill('Demo Tester');
  await page.getByLabel('Shipping email', { exact: true }).fill('tester@example.test');
  await page.getByLabel('Shipping address', { exact: true }).fill('123 Example Street');
  await page.getByRole('button', { name: 'Place demo order', exact: true }).click();
}

test('actual login cart checkout confirms an order without a payment', async ({ page }) => {
  await setup(page);
  await login(page);
  await expect(page.getByText('Logged In Successfully', { exact: true })).toBeVisible();
  await checkout(page);
  await expect(page.getByRole('heading', { name: 'Order confirmed' })).toBeVisible();
  await expect(page.getByText('Demo order · no payment taken')).toBeVisible();
});

test('registration signs in the session account and refuses duplicates and bad credentials', async ({ page }) => {
  await setup(page);
  await login(page, 'wrong-demo-value');
  await expect(page.getByRole('alert')).toHaveText('Invalid credentials. Please try again.');
  await page.getByRole('button', { name: 'Register', exact: true }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Demo Registrant');
  await page.getByLabel('Registration email', { exact: true }).fill('new@example.test');
  await page.getByLabel('Registration password', { exact: true }).fill('Synthetic123!');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByText('Account created. Please sign in.')).toBeVisible();
  await page.getByLabel('Password', { exact: true }).fill('Synthetic123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByText('Logged In Successfully', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await page.getByRole('button', { name: 'Register', exact: true }).click();
  await page.getByLabel('Display name').fill('Duplicate');
  await page.getByLabel('Registration email').fill('new@example.test');
  await page.getByLabel('Registration password').fill('Synthetic123!');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('alert')).toHaveText('An account with this email already exists.');
});

test('controlled locator change is observable and real checkout rejection never confirms', async ({ page }) => {
  const scenario = await setup(page);
  await page.request.patch(`/api/demo-lab/scenarios/${scenario.id}`, { data: { locator_revision: 1, visual_variant: true, checkout_failure: true } });
  await page.reload();
  await login(page);
  await page.getByRole('button', { name: 'Add Studio Notebook to cart' }).click();
  await page.getByRole('button', { name: 'View cart', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Checkout', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Continue to shipping' }).click();
  await page.getByLabel('Full name').fill('Demo Tester');
  await page.getByLabel('Shipping email').fill('tester@example.test');
  await page.getByLabel('Shipping address').fill('123 Example Street');
  await page.getByRole('button', { name: 'Place demo order' }).click();
  await expect(page.getByRole('alert')).toHaveText('Checkout unavailable: inventory service rejected the order.');
  await expect(page.getByRole('heading', { name: 'Order confirmed' })).not.toBeVisible();
  await expect(page.locator('body')).toHaveClass('visual-change');
});
