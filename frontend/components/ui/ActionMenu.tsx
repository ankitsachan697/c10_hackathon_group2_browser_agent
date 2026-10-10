"use client";
import { useState } from "react";
import { MoreHorizontal } from "lucide-react";

export function ActionMenu({ label = "Actions", children }: { label?: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return <div className="action-menu"><button aria-label={label} className="icon-button" onClick={() => setOpen(v => !v)}><MoreHorizontal size={18} /></button>{open && <div className="action-menu-popover" onClick={() => setOpen(false)}>{children}</div>}</div>;
}
