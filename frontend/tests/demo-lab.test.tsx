import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import DemoLabPage from '@/app/demo-lab/page';

test('switch changes immediately while the server saves, then rolls back a rejected update', async () => {
  let rejectUpdate: (error: Error) => void = () => undefined;
  vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo, init?: RequestInit) => {
    if (init?.method === 'PATCH') return await new Promise<Response>((_resolve, reject) => { rejectUpdate = reject; });
    return new Response(JSON.stringify({ data: [{ id: 'scenario', target_path: '/api/demo-shop/scenario', locator_revision: 0, visual_variant: false, checkout_failure: false }] }));
  }));
  render(<DemoLabPage/>);
  const toggle = await screen.findByRole('checkbox', { name: /Change checkout locator/ });
  await waitFor(() => expect(toggle).toBeEnabled());
  fireEvent.click(toggle);
  expect(toggle).toBeChecked();
  rejectUpdate(new TypeError('Failed to fetch'));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(toggle).not.toBeChecked();
});
