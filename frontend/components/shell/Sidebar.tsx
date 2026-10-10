"use client";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarClock, FolderKanban, Gauge, History, Settings } from "lucide-react";

const items = [["/", "Overview", Gauge], ["/projects", "Projects", FolderKanban], ["/runs", "Runs", History], ["/schedules", "Schedules", CalendarClock], ["/settings", "Settings", Settings]] as const;
export function Sidebar() {
  const pathname = usePathname();
  return <aside className="sidebar"><div className="brand"><Image src="/outskill-logo.svg" alt="Outskill" width={136} height={34} priority /><span>Browser Automation Studio</span></div><nav aria-label="Primary navigation">{items.map(([href, label, Icon]) => <Link key={href} href={href} className={pathname === href ? "nav-link active" : "nav-link"}><Icon size={18}/><span>{label}</span></Link>)}</nav><div className="sidebar-foot"><span className="pulse-dot"/>Ready for runs</div></aside>;
}
