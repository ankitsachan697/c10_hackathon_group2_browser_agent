import { Button } from "./Button";

export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onClose }: { open: boolean; title: string; children: React.ReactNode; confirmLabel: string; onConfirm: () => void; onClose: () => void }) {
  if (!open) return null;
  return <div className="dialog-backdrop"><div role="dialog" aria-modal="true" aria-labelledby="dialog-title" className="dialog">
    <h2 id="dialog-title">{title}</h2><div className="muted">{children}</div>
    <div className="dialog-actions"><Button onClick={onClose} className="button-secondary">Cancel</Button><Button onClick={onConfirm} className="button-danger">{confirmLabel}</Button></div>
  </div></div>;
}
