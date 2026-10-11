import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/shell/AppShell";

export const metadata: Metadata = {
  title: "Browser Automation Studio | Outskill",
  description: "Create, schedule, run, and repair browser journeys.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className="h-full antialiased"
    >
      <body suppressHydrationWarning><AppShell>{children}</AppShell></body>
    </html>
  );
}
