"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, Server, Timer, Workflow } from "lucide-react";
import { backendUrl } from "@/lib/api";
type Health={status:string;runner_ready:boolean;scheduler_ready:boolean;n8n_connected:boolean;browser_mode?:string};
export function Header() { const[health,setHealth]=useState<Health|null>(null);useEffect(()=>{fetch(`${backendUrl}/api/health`).then(r=>r.ok?r.json():Promise.reject()).then(setHealth).catch(()=>setHealth(null))},[]);const state=(ready:boolean|undefined)=>ready?"healthy":"offline";return <header className="topbar"><div className="health"><span className={state(health?.status==="healthy")}><Server size={14}/>API</span><span className={state(health?.runner_ready)}><Timer size={14}/>Runner</span><span className={state(health?.scheduler_ready)}><Workflow size={14}/>Scheduler</span><span className={state(health?.n8n_connected)}><Workflow size={14}/>n8n</span></div><Link href="/journeys/new" className="button primary-link"><Plus size={16}/>New journey</Link></header>; }
