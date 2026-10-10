import Link from "next/link";
import { Plus, Server, Timer, Workflow } from "lucide-react";
export function Header() { return <header className="topbar"><div className="health"><span><Server size={14}/>API</span><span><Timer size={14}/>Runner</span><span><Workflow size={14}/>Scheduler</span><span><Workflow size={14}/>n8n</span></div><Link href="/journeys/new" className="button primary-link"><Plus size={16}/>New journey</Link></header>; }
