"""
FastAPI Server for AI Self-Healing Browser Automation System.
Exposes REST endpoints for:
- Standalone Flow Discovery & Script Generation
- Standalone Execution Agent (Playwright)
- Standalone Error Diagnosis & Adaptive Repair
- Standalone Visual Regression Monitor (Pixelmatch)
- Full End-to-End Autonomous Self-Healing Pipeline
- Real-time Log Streaming & Artifact Serving
"""

import os
import sys

# Auto-reexec with local project virtualenv if executed with system python
venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
if os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
    try:
        import fastapi
    except ImportError:
        os.execv(venv_python, [venv_python] + sys.argv)

import json
import time
import asyncio
from dataclasses import replace
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# Add current dir to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Settings
from runner import PlaywrightRunner
from visual_diff import compare_images
from n8n_client import N8nClient
from test_suite_manager import suite_manager
from failure_context import build_failure_packet
from database import Database
from orchestrator import RunOrchestrator
from scheduler import APSchedulerAdapter, ScheduleService
from artifact_store import ArtifactStore
from repositories import ArtifactRepository
try:
    from backend.api import install_api
    from backend.api.context import AppServices
except ImportError:
    from api import install_api
    from api.context import AppServices

settings = Settings.from_env()
n8n_client = N8nClient(settings)
schedule_service = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    if schedule_service:
        schedule_service.start()
        application.state.scheduler_ready = True
    else:
        application.state.scheduler_ready = False
    try:
        yield
    finally:
        if schedule_service:
            schedule_service.shutdown()
        application.state.scheduler_ready = False

app = FastAPI(
    title=settings.product_name or "API",
    description="Backend orchestration engine for browser automation agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ARTIFACTS_DIR = str(settings.artifacts_root)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
runner = PlaywrightRunner(artifacts_dir=ARTIFACTS_DIR)
domain_database = Database(settings.database_path)
domain_database.initialize()
if settings.runner_timeout_seconds is not None:
    run_orchestrator = RunOrchestrator(domain_database, runner, n8n_client, settings.runner_timeout_seconds)
    schedule_service = ScheduleService(domain_database, run_orchestrator, APSchedulerAdapter())
else:
    run_orchestrator = None
artifact_store = ArtifactStore(settings.artifacts_root, settings.artifact_trash_root, ArtifactRepository(domain_database))

# In-memory log buffer for streaming logs to frontend
active_run_logs: Dict[str, List[Dict[str, Any]]] = {}


# --- Request Models ---
class DiscoveryRequest(BaseModel):
    url: str
    task_objective: str
    credentials_meta: Optional[Dict[str, Any]] = None


class ExecuteRequest(BaseModel):
    script: str
    env_vars: Optional[Dict[str, str]] = None
    secrets_to_mask: Optional[List[str]] = None
    headed: bool = False
    timeout_seconds: int | None = settings.runner_timeout_seconds


class RepairRequest(BaseModel):
    original_script: str
    error_trace: str
    dom_snapshot: Optional[str] = ""
    screenshot_path: Optional[str] = ""


class VisualDiffRequest(BaseModel):
    baseline_path: str
    candidate_path: str
    threshold: float | None = settings.visual_diff_threshold
    tolerance_percent: float | None = settings.visual_tolerance_percent


class AutonomousRunRequest(BaseModel):
    url: str
    task_objective: str
    username: Optional[str] = None
    password: Optional[str] = None
    max_repair_attempts: Optional[int] = None
    run_visual_regression: bool = True
    headed: bool = False
    test_case_name: Optional[str] = None


class ExecuteScriptRequest(BaseModel):
    script: str
    url: Optional[str] = None
    test_name: Optional[str] = None
    headed: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: int | None = settings.runner_timeout_seconds
    auto_heal: bool = True


class SaveTestCaseRequest(BaseModel):
    id: Optional[str] = None
    project: str = "Default"
    name: str
    target_url: str
    objective: str
    script: str
    username: Optional[str] = None
    schedule: Optional[str] = "Manual"


from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, WebSocket, WebSocketDisconnect

# --- Endpoints ---

def _require_runner_timeout(timeout_seconds: int | None) -> int:
    if timeout_seconds is None:
        raise HTTPException(status_code=503, detail="RUNNER_TIMEOUT_SECONDS is not configured")
    return timeout_seconds


def _visual_settings_available() -> bool:
    return settings.visual_diff_threshold is not None and settings.visual_tolerance_percent is not None

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "runner_ready": settings.runner_timeout_seconds is not None,
        "n8n_connected": n8n_client.is_configured,
        "scheduler_ready": bool(schedule_service and getattr(app.state, "scheduler_ready", False)),
    }


@app.websocket("/ws/session")
async def websocket_session_endpoint(websocket: WebSocket):
    """Graceful WebSocket handler for browser extensions and live session probes."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"status": "active", "received": True})
    except WebSocketDisconnect:
        pass


@app.get("/ws/session")
async def get_session_fallback():
    """HTTP fallback for clients probing /ws/session without upgrade headers."""
    return {"status": "active", "websocket_available": True}


@app.post("/api/discovery-and-generate")
async def discovery_and_generate(req: DiscoveryRequest):
    """Standalone Agent 1: Flow Discovery & Script Generator"""
    result = n8n_client.generate_flow_script(
        url=req.url,
        task_objective=req.task_objective,
        credentials_meta=req.credentials_meta,
    )
    return result


@app.post("/api/execute")
async def execute_script(req: ExecuteRequest):
    """Standalone Agent 2: Execution Agent (Python Playwright)"""
    run_id = f"run_{int(time.time())}"
    active_run_logs[run_id] = []

    def on_log(log_item):
        active_run_logs[run_id].append(log_item)

    res = await runner.execute_script(
        script_code=req.script,
        env_vars=req.env_vars,
        secrets_to_mask=req.secrets_to_mask,
        timeout_seconds=_require_runner_timeout(req.timeout_seconds),
        headed=req.headed,
        on_log=on_log,
    )
    return res


@app.post("/api/diagnose-and-repair")
async def diagnose_and_repair(req: RepairRequest):
    """Standalone Agent 3: Error Diagnosis & Adaptive Repair"""
    packet = replace(build_failure_packet({
        "stderr": req.error_trace,
        "dom_snapshot": req.dom_snapshot or "",
        "screenshots": [req.screenshot_path] if req.screenshot_path else [],
    }), original_script=req.original_script)
    res = n8n_client.diagnose_and_repair(packet)
    return res


@app.post("/api/visual-diff")
async def visual_diff(req: VisualDiffRequest):
    """Standalone Agent 4: Visual Regression Monitor (Pixelmatch)"""
    if req.threshold is None or req.tolerance_percent is None:
        raise HTTPException(status_code=503, detail="Visual comparison thresholds are not configured")

    diff_filename = f"diff_{int(time.time())}.png"
    diff_path = os.path.join(ARTIFACTS_DIR, diff_filename)

    res = compare_images(
        baseline_path=req.baseline_path,
        candidate_path=req.candidate_path,
        output_diff_path=diff_path,
        threshold=req.threshold,
        tolerance_percent=req.tolerance_percent,
    )
    res["diff_image_filename"] = diff_filename
    return res


@app.post("/api/autonomous-run")
async def autonomous_run(req: AutonomousRunRequest):
    """
    Full End-to-End Autonomous Pipeline:
    Discovery & Script Gen -> Execution -> If Fail: Diagnosis & Auto-Repair Loop -> Visual Regression
    """
    raise HTTPException(
        status_code=410,
        detail="Autonomous generate-and-run was retired. Save a generated journey, then execute its saved script.",
    )
    run_id = f"journey_{int(time.time())}"
    active_run_logs[run_id] = []

    def append_log(level: str, agent: str, msg: str):
        # Mask password in log string
        clean_msg = msg
        if req.password:
            clean_msg = clean_msg.replace(req.password, "[REDACTED_SECRET:••••••••]")
        active_run_logs[run_id].append({
            "timestamp": time.strftime("%H:%M:%S"),
            "level": level,
            "agent": agent,
            "message": clean_msg,
        })

    append_log("INFO", "Orchestrator", f"🚀 Starting Autonomous Self-Healing Journey for: {req.url}")
    append_log("INFO", "Flow Discovery Agent", f"Analyzing target domain and user objective: '{req.task_objective}'")

    # Passwords to mask
    secrets = [s for s in [req.password, req.username] if s]
    env_vars = {}
    if req.username:
        env_vars["AUTH_USERNAME"] = req.username
    if req.password:
        env_vars["AUTH_PASSWORD"] = req.password

    # Step 1: Flow Discovery & Script Generator
    discovery_res = n8n_client.generate_flow_script(
        url=req.url,
        task_objective=req.task_objective,
        credentials_meta={"has_auth": bool(req.password)},
    )
    current_script = discovery_res["python_script"]
    append_log("INFO", "Script Generator Agent", f"Generated Python Playwright script with {len(discovery_res['discovered_steps'])} steps.")

    # Execution Loop with Adaptive Self-Healing
    attempt = 1
    max_attempts = 1 + settings.auto_repair_retries
    last_exec_res = None
    healing_history = []

    while attempt <= max_attempts:
        append_log("INFO", "Execution Agent", f"Executing run attempt #{attempt} (headed={req.headed})...")
        
        def run_log_cb(log_item):
            active_run_logs[run_id].append(log_item)

        last_exec_res = await runner.execute_script(
            script_code=current_script,
            env_vars=env_vars,
            secrets_to_mask=secrets,
            timeout_seconds=_require_runner_timeout(settings.runner_timeout_seconds),
            headed=req.headed,
            on_log=run_log_cb,
        )

        if last_exec_res["passed"]:
            append_log("INFO", "Execution Agent", f"🎉 Test journey passed successfully on attempt #{attempt}!")
            break

        append_log("ERROR", "Execution Agent", f"❌ Execution failed on attempt #{attempt}. Invoking Self-Healing...")

        if attempt >= max_attempts:
            append_log("ERROR", "Orchestrator", f"Reached maximum repair attempts ({max_attempts}). Stopping.")
            break

        # Step 2: Error Diagnosis & Adaptive Repair Agent
        append_log("WARN", "Error Diagnosis Agent", "Analyzing stack trace, failure screenshot, and DOM snapshot...")
        repair_res = n8n_client.diagnose_and_repair(replace(
            build_failure_packet(last_exec_res, secrets=secrets), original_script=current_script
        ))

        append_log("WARN", "Error Diagnosis Agent", f"Root Cause: {repair_res['root_cause']}")
        append_log("INFO", "Adaptive Repair Agent", f"Applying fix: {repair_res['recommended_fix']}")

        healing_history.append({
            "attempt": attempt,
            "root_cause": repair_res["root_cause"],
            "fix": repair_res["recommended_fix"],
            "diff_summary": repair_res["diff_summary"],
        })

        current_script = repair_res["repaired_script"]
        attempt += 1

    # Step 3: Visual Regression Monitor Agent (Smart Golden Baseline Lifecycle)
    visual_res = None
    if req.run_visual_regression and last_exec_res and last_exec_res["screenshots"] and _visual_settings_available():
        append_log("INFO", "Regression Monitor Agent", "Evaluating Golden Baseline & Visual Regression...")
        visual_res = suite_manager.handle_visual_baseline_lifecycle(
            url=req.url,
            test_case_name=req.test_case_name or req.task_objective[:30],
            screenshots=last_exec_res["screenshots"],
            run_dir=last_exec_res["run_dir"],
            threshold=settings.visual_diff_threshold,
            tolerance_percent=settings.visual_tolerance_percent,
        )
        append_log("INFO", "Regression Monitor Agent", visual_res["summary"])

    append_log("INFO", "Orchestrator", "Self-healing journey sequence finished.")

    actual_run_id = last_exec_res["run_id"] if last_exec_res else run_id

    # Record in Run History
    suite_manager.record_run({
        "run_id": actual_run_id,
        "url": req.url,
        "name": req.test_case_name or req.task_objective[:40],
        "status": "PASSED" if (last_exec_res and last_exec_res["passed"]) else "FAILED",
        "duration": last_exec_res["duration_seconds"] if last_exec_res else 0,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "screenshots": last_exec_res["screenshots"] if last_exec_res else [],
        "video": last_exec_res.get("video") if last_exec_res else None,
        "visual_status": visual_res.get("status") if visual_res else None,
        "attempts": attempt,
    })

    return {
        "run_id": actual_run_id,
        "success": last_exec_res["passed"] if last_exec_res else False,
        "attempts": attempt,
        "discovered_steps": discovery_res["discovered_steps"],
        "final_script": current_script,
        "execution_result": last_exec_res,
        "healing_history": healing_history,
        "visual_regression": visual_res,
        "logs": active_run_logs.get(run_id, []),
    }


@app.post("/api/execute-script")
async def execute_direct_script(req: ExecuteScriptRequest):
    """
    Direct Script Execution:
    Validates and runs the exact Python Playwright script currently in the viewer/editor.
    If execution fails and auto_heal is True, the Error Diagnosis and Adaptive Repair agents
    are invoked automatically to diagnose the failure, repair the script, and re-execute.
    """
    run_id = f"direct_{int(time.time())}"
    active_run_logs[run_id] = []

    def on_log(log_item):
        active_run_logs[run_id].append(log_item)

    active_run_logs[run_id].append({
        "timestamp": time.strftime("%H:%M:%S"),
        "level": "INFO",
        "agent": "Execution Agent",
        "message": f"🚀 Starting direct script validation run (headed={req.headed})...",
    })

    env_vars = {}
    secrets = []
    if req.username:
        env_vars["AUTH_USERNAME"] = req.username
    if req.password:
        env_vars["AUTH_PASSWORD"] = req.password
        secrets.append(req.password)

    current_script = req.script
    timeout_seconds = _require_runner_timeout(req.timeout_seconds)
    exec_res = await runner.execute_script(
        script_code=current_script,
        env_vars=env_vars,
        secrets_to_mask=secrets,
        timeout_seconds=timeout_seconds,
        headed=req.headed,
        on_log=on_log,
    )

    healing_history = []
    healed_script = None

    # Auto-heal loop if run failed
    if not exec_res["passed"] and req.auto_heal:
        on_log({
            "timestamp": time.strftime("%H:%M:%S"),
            "level": "WARN",
            "agent": "Error Diagnosis Agent",
            "message": "❌ Direct execution failed. Automatically invoking Error Diagnosis Agent...",
        })

        repair_res = n8n_client.diagnose_and_repair(replace(
            build_failure_packet(exec_res, secrets=secrets), original_script=current_script
        ))

        on_log({
            "timestamp": time.strftime("%H:%M:%S"),
            "level": "WARN",
            "agent": "Error Diagnosis Agent",
            "message": f"Root Cause: {repair_res['root_cause']}",
        })
        on_log({
            "timestamp": time.strftime("%H:%M:%S"),
            "level": "INFO",
            "agent": "Adaptive Repair Agent",
            "message": f"Synthesized Patch: {repair_res['recommended_fix']}",
        })

        healing_history.append(repair_res)
        healed_script = repair_res["repaired_script"]
        current_script = healed_script

        on_log({
            "timestamp": time.strftime("%H:%M:%S"),
            "level": "INFO",
            "agent": "Execution Agent",
            "message": "Re-validating healed Playwright script...",
        })

        retest_res = await runner.execute_script(
            script_code=current_script,
            env_vars=env_vars,
            secrets_to_mask=secrets,
            timeout_seconds=timeout_seconds,
            headed=req.headed,
            on_log=on_log,
        )

        if retest_res["passed"]:
            exec_res = retest_res
            on_log({
                "timestamp": time.strftime("%H:%M:%S"),
                "level": "INFO",
                "agent": "Adaptive Repair Agent",
                "message": "🎉 Healed script passed validation successfully!",
            })
        else:
            exec_res = retest_res

    # Check Visual Regression / Golden Baseline Lifecycle
    visual_res = None
    if exec_res.get("screenshots") and req.url and _visual_settings_available():
        visual_res = suite_manager.handle_visual_baseline_lifecycle(
            url=req.url,
            test_case_name=req.test_name or "",
            screenshots=exec_res["screenshots"],
            run_dir=exec_res["run_dir"],
            threshold=settings.visual_diff_threshold,
            tolerance_percent=settings.visual_tolerance_percent,
        )
        on_log({
            "timestamp": time.strftime("%H:%M:%S"),
            "level": "INFO",
            "agent": "Regression Monitor Agent",
            "message": visual_res["summary"],
        })

    # Record in history
    actual_run_id = exec_res["run_id"]
    suite_manager.record_run({
        "run_id": actual_run_id,
        "url": req.url,
        "name": req.test_name,
        "status": exec_res["status"],
        "duration": exec_res["duration_seconds"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "screenshots": exec_res["screenshots"],
        "video": exec_res.get("video"),
        "visual_status": visual_res.get("status") if visual_res else None,
        "attempts": len(healing_history) + 1,
    })

    return {
        "run_id": actual_run_id,
        "status": exec_res["status"],
        "passed": exec_res["passed"],
        "execution_result": exec_res,
        "final_script": current_script,
        "healed_script": healed_script,
        "healing_history": healing_history,
        "visual_regression": visual_res,
        "logs": active_run_logs.get(run_id, []),
    }


# --- Test Suite & Run History Endpoints ---

@app.get("/api/test-cases")
def list_test_cases():
    return {"cases": suite_manager.get_test_cases()}


@app.post("/api/test-cases")
def save_test_case(req: SaveTestCaseRequest):
    saved = suite_manager.save_test_case(req.dict())
    return {"ok": True, "case": saved}


@app.delete("/api/test-cases/{case_id}")
def delete_test_case(case_id: str):
    ok = suite_manager.delete_test_case(case_id)
    return {"ok": ok}


@app.post("/api/test-cases/{case_id}/run")
async def run_saved_test_case(case_id: str, headed: bool = False):
    """Executes a saved test case by its ID and records results."""
    case = suite_manager.get_test_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")

    exec_req = ExecuteScriptRequest(
        script=case.get("script", ""),
        url=case.get("target_url"),
        test_name=case.get("name"),
        headed=headed,
        username=case.get("username"),
        password=case.get("password"),
        auto_heal=True,
    )
    result = await execute_direct_script(exec_req)
    # Update last_run_status
    case["last_run_status"] = "PASSED" if result["passed"] else "FAILED"
    case["last_run_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    suite_manager.save_test_case(case)
    return result


@app.get("/api/legacy/runs")
def list_runs():
    return {"runs": suite_manager.get_run_history()}


@app.get("/api/logs/{run_id}")
def get_logs(run_id: str):
    return {"run_id": run_id, "logs": active_run_logs.get(run_id, [])}


@app.get("/api/artifacts/{file_path:path}")
def get_artifact(file_path: str):
    """
    Universal artifact server.
    Serves screenshots, pixelmatch diffs, golden baselines, and WebM video recordings.
    """
    # 1. Direct path in artifacts directory
    candidate_path = os.path.join(ARTIFACTS_DIR, file_path)
    if os.path.exists(candidate_path) and os.path.isfile(candidate_path):
        media_type = "video/webm" if candidate_path.endswith(".webm") else None
        return FileResponse(candidate_path, media_type=media_type)

    # 2. Check by filename across newest run directories
    basename = os.path.basename(file_path)
    try:
        subdirs = sorted(
            [os.path.join(ARTIFACTS_DIR, d) for d in os.listdir(ARTIFACTS_DIR) if os.path.isdir(os.path.join(ARTIFACTS_DIR, d))],
            key=os.path.getmtime,
            reverse=True
        )
        for sub in subdirs:
            cand = os.path.join(sub, basename)
            if os.path.exists(cand) and os.path.isfile(cand):
                media_type = "video/webm" if cand.endswith(".webm") else None
                return FileResponse(cand, media_type=media_type)
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Artifact not found: {file_path}")


app.state.settings = settings
app.state.services = AppServices(
    database=domain_database,
    orchestrator=run_orchestrator,
    scheduler=schedule_service,
    artifacts=artifact_store,
    agents=n8n_client,
)
install_api(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
