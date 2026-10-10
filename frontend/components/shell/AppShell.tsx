import { Suspense } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { ToastProvider } from "../ui/ToastProvider";
export function AppShell({ children }: { children: React.ReactNode }) { return <ToastProvider><div className="app-shell"><Suspense fallback={<aside className="sidebar" aria-label="Loading navigation"/>}><Sidebar/></Suspense><div className="workspace"><Header/><main>{children}</main></div></div></ToastProvider>; }
