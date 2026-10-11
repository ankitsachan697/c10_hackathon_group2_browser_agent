import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import OverviewPage from '@/app/page';
import RunsPage from '@/app/runs/page';
import { RunVisual } from '@/components/runs/RunVisual';
import type { Run } from '@/lib/types';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo, init?: RequestInit) => {
    const path = String(url);
    const data = path.includes('overview') ? { pass_rate: 66.7, needs_attention: 1, repaired_runs: 1, active_runs: 0, total_runs: 3, completed_runs: 3, projects: 1, journeys: 2, next_schedule: null }
      : init?.method === 'DELETE' ? { deleted: true } : [{ id: 'run_demo', status: 'PASSED', trigger_source: 'ON_DEMAND', attempt_count: 1 }];
    return new Response(JSON.stringify({ data }));
  }));
});
test('overview renders persisted metrics rather than placeholder counts', async () => {
  render(<OverviewPage/>);
  expect(await screen.findByText('66.7%')).toBeInTheDocument();
  expect(screen.getByText('3 completed runs')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open demo lab' })).toHaveAttribute('href', '/demo-lab');
});
test('history deletion requires confirmation then removes the completed row', async () => {
  render(<RunsPage/>);
  expect(await screen.findByRole('link', { name: 'run_demo' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Actions for run_demo' }));
  fireEvent.click(screen.getByRole('menuitem', { name: 'Delete run' }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Delete run' }));
  await waitFor(() => expect(screen.queryByRole('link', { name: 'run_demo' })).not.toBeInTheDocument());
});
test('visual evidence presents baseline current and difference images inline', () => {
  render(<RunVisual run={{ id: 'run', created_at: '2026-10-11T00:00:00Z', status: 'PASSED', trigger_source: 'ON_DEMAND', attempt_count: 1, visual_outcome: 'DIFFERENCE', visual_review: { baseline_artifact_id: 'b', candidate_artifact_id: 'c', diff_artifact_id: 'd', mismatch_percentage: 12.3 } } as Run}/>);
  expect(screen.getByRole('img', { name: 'Baseline screenshot' })).toHaveAttribute('src', '/api/artifacts/b');
  expect(screen.getByRole('img', { name: 'Current screenshot' })).toHaveAttribute('src', '/api/artifacts/c');
  expect(screen.getByRole('img', { name: 'Difference heatmap' })).toHaveAttribute('src', '/api/artifacts/d');
});
