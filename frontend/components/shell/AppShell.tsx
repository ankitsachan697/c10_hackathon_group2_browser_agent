import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { ToastProvider } from "../ui/ToastProvider";
export function AppShell({ children }: { children: React.ReactNode }) { return <ToastProvider><div className="app-shell"><Sidebar/><div className="workspace"><Header/><main>{children}</main></div></div></ToastProvider>; }
