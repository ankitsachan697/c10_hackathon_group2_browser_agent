"use client";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreHorizontal } from "lucide-react";

export function ActionMenu({ label = "Actions", children }: { label?: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const position = useCallback(() => {
    if (!trigger.current || !popover.current) return;
    const anchor = trigger.current.getBoundingClientRect();
    const menu = popover.current;
    const margin = 8;
    menu.style.maxHeight = `${window.innerHeight - margin * 2}px`;
    const size = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(margin, Math.min(anchor.right - size.width, window.innerWidth - size.width - margin))}px`;
    menu.style.top = `${Math.max(margin, anchor.bottom + size.height + margin > window.innerHeight ? anchor.top - size.height - 6 : anchor.bottom + 6)}px`;
  }, []);
  useLayoutEffect(() => {
    if (!open) return;
    position();
    popover.current?.querySelector<HTMLElement>('[role="menuitem"]:not(:disabled)')?.focus();
  }, [open, position]);
  useEffect(() => {
    if (!open) return;
    const dismiss = () => { setOpen(false); trigger.current?.focus(); };
    const outside = (event: PointerEvent) => {
      if (!popover.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setOpen(false);
    };
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); dismiss(); }
      if (event.key === "Tab") { setOpen(false); trigger.current?.focus(); }
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const items = Array.from(popover.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? []);
        const index = items.indexOf(document.activeElement as HTMLElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items[next]?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", keydown);
    window.addEventListener("scroll", position, true);
    window.addEventListener("resize", dismiss);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", keydown);
      window.removeEventListener("scroll", position, true);
      window.removeEventListener("resize", dismiss);
    };
  }, [open, position]);
  return <div className="action-menu" onClick={event => event.stopPropagation()}>
    <button ref={trigger} type="button" aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined} className="icon-button" onClick={() => setOpen(v => !v)} onKeyDown={event => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setOpen(true); }
    }}><MoreHorizontal size={18} /></button>
    {open && createPortal(<div ref={popover} id={menuId} role="menu" aria-label={label} className="action-menu-popover" onClick={event => {
      event.stopPropagation(); setOpen(false); trigger.current?.focus();
    }}>{children}</div>, document.body)}
  </div>;
}
