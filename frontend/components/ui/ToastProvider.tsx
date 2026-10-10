"use client";
import { createContext, useCallback, useContext, useState } from "react";

const ToastContext = createContext<(message: string) => void>(() => undefined);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState("");
  const notify = useCallback((value: string) => { setMessage(value); window.setTimeout(() => setMessage(""), 2600); }, []);
  return <ToastContext.Provider value={notify}>{children}{message && <div role="status" className="toast">{message}</div>}</ToastContext.Provider>;
}
export const useToast = () => useContext(ToastContext);
