import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import DemoLabPage from '@/app/demo-lab/page';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

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

test('remote demo journey uses the public backend URL rather than protected Studio origin', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ data: [{ id: 'scenario', target_path: '/api/demo-shop/scenario', target_url: 'https://controller.example/api/demo-shop/scenario', locator_revision: 0, visual_variant: false, checkout_failure: false }] }))));
  render(<DemoLabPage/>);
  const link = await screen.findByRole('link', { name: /Open demo shop/ });
  expect(link).toHaveAttribute('href', 'https://controller.example/api/demo-shop/scenario');
  expect(screen.getByTitle('Demo shop preview')).toHaveAttribute('src', 'https://controller.example/api/demo-shop/scenario');
});

test('an empty lab explains disabled controls and offers target creation in context', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ data: [] }))));
  render(<DemoLabPage/>);
  expect(await screen.findByRole('button', { name: 'Create demo target' })).toBeEnabled();
  expect(screen.getByText(/Create a demo target first/)).toBeInTheDocument();
});

test('replay offers only saved journeys for the selected target', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo) => {
    const data = String(url) === '/api/journeys' ? [
      { id: 'matching', name: 'Demo checkout', target_url: 'https://controller.example/api/demo-shop/scenario', active: 1, script: 'page.goto(target_url)' },
      { id: 'draft', name: 'Unverified draft', target_url: 'https://controller.example/api/demo-shop/scenario', active: 1, script: '' },
      { id: 'other', name: 'Other site', target_url: 'https://other.example/login', active: 1 },
    ] : [{ id: 'scenario', target_path: '/api/demo-shop/scenario', target_url: 'https://controller.example/api/demo-shop/scenario', locator_revision: 0, visual_variant: false, checkout_failure: false }];
    return new Response(JSON.stringify({ data }));
  }));
  render(<DemoLabPage/>);
  expect(await screen.findByRole('option', { name: 'Demo checkout' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Other site' })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Unverified draft' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Replay saved journey' })).toBeEnabled();
});

test('target cannot change while a saved replay is being admitted', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo, init?: RequestInit) => {
    if (init?.method === 'POST') return await new Promise<Response>(() => undefined);
    const data = String(url) === '/api/journeys'
      ? [{ id: 'matching', name: 'Demo checkout', target_url: 'https://controller.example/api/demo-shop/scenario', active: 1, script: 'page.goto(target_url)' }]
      : [{ id: 'scenario', target_path: '/api/demo-shop/scenario', target_url: 'https://controller.example/api/demo-shop/scenario', locator_revision: 0, visual_variant: false, checkout_failure: false }];
    return new Response(JSON.stringify({ data }));
  }));
  render(<DemoLabPage/>);
  await screen.findByRole('option', { name: 'Demo checkout' });
  fireEvent.click(screen.getByRole('button', { name: 'Replay saved journey' }));
  expect(screen.getByRole('checkbox', { name: /Change checkout locator/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'New scenario' })).toBeDisabled();
});
