"use client";

import type { ActivityEvent, Run } from "@/lib/types";
import { LiveRunProgress } from "@/components/runs/LiveRunProgress";

export function RunResultTabs({ run, runEvents }: { run: Run; runEvents: ActivityEvent[] }) {
  return <LiveRunProgress run={run} runEvents={runEvents} operationEvents={[]}/>;
}
