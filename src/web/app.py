"""FastAPI web frontend for the MBSE Model Generation System."""
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import src.config as config
from src.agent.chat import chat_with_agent
from src.agent.tools import apply_tool
from src.cost_tracker import CostTracker
from src.exporter import export_json, export_xlsx, export_text
from src.models import MBSEModel, ProjectModel, Requirement
from src.parser import parse_requirements_file
from src.pipeline import estimate_cost, merge_batch_into_project, run_pipeline
from src.project import (
    backup_project,
    get_project_path,
    load_project,
    new_project as create_new_project,
    save_project,
)

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent
app = FastAPI(title="mbse")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")

# In-memory state
jobs: dict[str, "Job"] = {}
parsed_requirements: list[Requirement] = []
current_project: ProjectModel | None = load_project()

from src.config import MODEL_CATALOGUE, CAPELLA_LAYERS, RHAPSODY_DIAGRAMS


@dataclass
class Job:
    id: str
    status: str = "pending"  # pending, analyzing, running, clarification_needed, complete, failed, cancelled
    requirements: list = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    model: MBSEModel | ProjectModel | None = None
    cancelled: bool = False
    task: asyncio.Task | None = None
    conversation_history: list[dict] = field(default_factory=list)

    def emit(self, event: dict):
        self.events.append(event)


def _reload_config():
    """Reload config from .env after settings change."""
    from dotenv import load_dotenv
    env_path = config.PACKAGE_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
    cwd_env = config.CWD / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=True)
    config.PROVIDER = os.getenv("PROVIDER", "anthropic")
    config.MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
    config.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    config.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        version_path = config.PACKAGE_ROOT / "pyproject.toml"
        version = "unknown"
        if version_path.exists():
            for line in version_path.read_text().splitlines():
                if line.strip().startswith("version"):
                    version = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        version = "unknown"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": version,
        "model_catalogue": MODEL_CATALOGUE,
        "capella_layers": CAPELLA_LAYERS,
        "rhapsody_diagrams": RHAPSODY_DIAGRAMS,
        "settings": {
            "provider": config.PROVIDER,
            "model": config.MODEL,
            "default_mode": config.DEFAULT_MODE,
            "has_anthropic_key": bool(config.ANTHROPIC_API_KEY),
            "has_openrouter_key": bool(config.OPENROUTER_API_KEY),
        },
        "project": current_project.model_dump() if current_project else None,
    })


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global parsed_requirements

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Use .xlsx, .xls, or .csv")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        reqs = parse_requirements_file(tmp_path)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Failed to parse file: {exc}")

    tmp_path.unlink(missing_ok=True)
    parsed_requirements = reqs
    return {
        "count": len(reqs),
        "requirements": [r.model_dump() for r in reqs],
    }


# ---------------------------------------------------------------------------
# GET /project
# ---------------------------------------------------------------------------

@app.get("/project")
async def get_project():
    if current_project is None:
        return {"project": None}
    return current_project.model_dump()


# ---------------------------------------------------------------------------
# POST /project/new
# ---------------------------------------------------------------------------

@app.post("/project/new")
async def create_project(request: Request):
    global current_project
    body = await request.json()
    name = body.get("name", "Untitled Project")
    mode = body.get("mode", config.DEFAULT_MODE)

    # Backup existing project if it has data
    if current_project and (current_project.batches or current_project.requirements):
        backup_project()

    current_project = create_new_project(mode, name)
    save_project(current_project)
    return current_project.model_dump()


# ---------------------------------------------------------------------------
# POST /project/rename
# ---------------------------------------------------------------------------

@app.post("/project/rename")
async def rename_project(request: Request):
    global current_project
    if not current_project:
        raise HTTPException(400, "No active project")
    body = await request.json()
    current_project.project.name = body.get("name", current_project.project.name)
    save_project(current_project)
    return {"name": current_project.project.name}


# ---------------------------------------------------------------------------
# GET /project/batches
# ---------------------------------------------------------------------------

@app.get("/project/batches")
async def get_batches():
    if not current_project:
        return {"batches": []}
    return {"batches": [b.model_dump() for b in current_project.batches]}


# ---------------------------------------------------------------------------
# POST /estimate
# ---------------------------------------------------------------------------

@app.post("/estimate")
async def estimate(request: Request):
    body = await request.json()
    mode = body.get("mode", "capella")
    selected_layers = body.get("selected_layers", [])
    model = body.get("model", config.MODEL)

    if not parsed_requirements:
        raise HTTPException(400, "No requirements loaded. Upload a file first.")
    if not selected_layers:
        raise HTTPException(400, "No layers selected.")

    result = estimate_cost(parsed_requirements, mode, selected_layers, model)
    return result


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------

@app.post("/run")
async def run(request: Request):
    global parsed_requirements

    if not parsed_requirements:
        raise HTTPException(400, "No requirements loaded. Upload a file first.")

    body = await request.json()
    mode = body.get("mode", "capella")
    selected_layers = body.get("selected_layers", [])
    model = body.get("model", config.MODEL)
    provider = body.get("provider", config.PROVIDER)
    clarifications = body.get("clarifications") or None
    source_file = body.get("source_file", "uploaded")

    # Feature 2: filter requirements by selected IDs if provided
    selected_req_ids = body.get("selected_requirements")
    reqs = list(parsed_requirements)
    if selected_req_ids:
        reqs = [r for r in reqs if r.id in set(selected_req_ids)]
    if not reqs:
        raise HTTPException(400, "No requirements selected. Check your requirement selection.")

    if not selected_layers:
        raise HTTPException(400, "No layers selected.")

    job = Job(
        id=str(uuid.uuid4())[:8],
        requirements=reqs,
        settings={
            "mode": mode,
            "selected_layers": selected_layers,
            "model": model,
            "provider": provider,
            "clarifications": clarifications,
            "source_file": source_file,
        },
    )
    jobs[job.id] = job
    job.task = asyncio.create_task(_run_job_async(job))
    return {"job_id": job.id}


# ---------------------------------------------------------------------------
# _run_job_async
# ---------------------------------------------------------------------------

async def _run_job_async(job: Job):
    """Run the MBSE pipeline in a thread and stream events via job.emit."""
    global current_project

    try:
        job.status = "running"
        settings = job.settings
        mode = settings["mode"]
        model_name = settings["model"]
        selected_layers = settings["selected_layers"]
        provider = settings["provider"]

        cost_log_path = config.OUTPUT_DIR / "cost_log.jsonl"

        # Create project if needed
        if current_project is None:
            current_project = create_new_project(mode, "Untitled Project")

        # Run pipeline with existing model context if project has data
        existing = current_project if current_project.batches else None

        def _do_work():
            return run_pipeline(
                requirements=job.requirements,
                mode=mode,
                selected_layers=selected_layers,
                model=model_name,
                provider=provider,
                clarifications=settings.get("clarifications"),
                existing_model=existing,
                emit=job.emit,
                cost_log_path=cost_log_path,
            )

        if job.cancelled:
            job.status = "cancelled"
            job.emit({"stage": "cancelled", "status": "cancelled", "detail": "Job was cancelled before starting"})
            return

        batch_result = await asyncio.to_thread(_do_work)

        if job.cancelled:
            job.status = "cancelled"
            job.emit({"stage": "cancelled", "status": "cancelled", "detail": "Job was cancelled"})
            return

        # Merge batch result into the project
        total_cost = batch_result.meta.cost.total_cost_usd if batch_result.meta.cost else 0
        merge_batch_into_project(
            current_project,
            batch_result.requirements,
            batch_result.layers,
            batch_result.links,
            batch_result.instructions,
            source_file=settings.get("source_file", "uploaded"),
            layers_generated=selected_layers,
            model_name=model_name,
            cost=total_cost,
        )
        save_project(current_project)

        # Job model is the full project
        job.model = current_project
        job.status = "complete"

    except Exception as exc:
        logger.error(f"Job {job.id} failed: {exc}", exc_info=True)
        job.status = "failed"
        job.emit({"stage": "error", "status": "error", "detail": str(exc)})


# ---------------------------------------------------------------------------
# GET /stream/{job_id}
# ---------------------------------------------------------------------------

@app.get("/stream/{job_id}")
async def stream(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        sent = 0
        while True:
            while sent < len(job.events):
                event = job.events[sent]
                yield f"data: {json.dumps(event)}\n\n"
                sent += 1
            if job.status in ("complete", "failed", "cancelled"):
                break
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /job/{job_id}
# ---------------------------------------------------------------------------

@app.get("/job/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "complete" or job.model is None:
        raise HTTPException(404, f"Job {job_id} is not complete (status: {job.status})")
    return job.model.model_dump()


# ---------------------------------------------------------------------------
# POST /job/{job_id}/edit
# ---------------------------------------------------------------------------

@app.post("/job/{job_id}/edit")
async def edit_job(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.model is None:
        raise HTTPException(400, "Job has no model to edit")

    body = await request.json()
    tool_name = body.get("tool_name")
    arguments = body.get("arguments", {})

    if not tool_name:
        raise HTTPException(400, "Missing 'tool_name' in request body")

    result = apply_tool(job.model, tool_name, arguments)
    if current_project:
        save_project(current_project)
    return result


# ---------------------------------------------------------------------------
# POST /job/{job_id}/chat
# ---------------------------------------------------------------------------

@app.post("/job/{job_id}/chat")
async def chat_job(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.model is None:
        raise HTTPException(400, "Job has no model to chat about")

    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(400, "Missing 'message' in request body")

    tracker = CostTracker(model=job.settings.get("model", config.MODEL))
    response_text, updated_history = chat_with_agent(
        model=job.model,
        user_message=message,
        conversation_history=job.conversation_history,
        tracker=tracker,
    )
    job.conversation_history = updated_history
    if current_project:
        save_project(current_project)

    return {
        "response": response_text,
        "model": job.model.model_dump(),
    }


# ---------------------------------------------------------------------------
# GET /job/{job_id}/export/{format}
# ---------------------------------------------------------------------------

@app.get("/job/{job_id}/export/{fmt}")
async def export_job(job_id: str, fmt: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.model is None:
        raise HTTPException(400, "Job has no model to export")

    fmt = fmt.lower()
    if fmt not in ("json", "xlsx", "text"):
        raise HTTPException(400, f"Unsupported format '{fmt}'. Use json, xlsx, or text")

    export_dir = config.OUTPUT_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Feature 4: smarter export filenames
    if current_project and current_project.project.name:
        source_stem = current_project.project.name.lower().replace(" ", "-")
    else:
        source_stem = Path(job.model.meta.source_file).stem if job.model.meta.source_file else "mbse"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    mode = job.model.meta.mode or "model"
    ext = "txt" if fmt == "text" else fmt
    filename = f"{source_stem}-{mode}-{timestamp}.{ext}"

    if fmt == "json":
        out_path = export_dir / f"{job_id}_model.json"
        export_json(job.model, out_path)
        return FileResponse(
            out_path,
            filename=filename,
            media_type="application/json",
        )
    elif fmt == "xlsx":
        out_path = export_dir / f"{job_id}_model.xlsx"
        export_xlsx(job.model, out_path)
        return FileResponse(
            out_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:  # text
        out_path = export_dir / f"{job_id}_model.txt"
        export_text(job.model, out_path)
        return FileResponse(
            out_path,
            filename=filename,
            media_type="text/plain",
        )


# ---------------------------------------------------------------------------
# POST /cancel/{job_id}
# ---------------------------------------------------------------------------

@app.post("/cancel/{job_id}")
async def cancel(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.cancelled = True
    if job.task and not job.task.done():
        job.task.cancel()
    return {"status": "cancelling"}


# ---------------------------------------------------------------------------
# GET /settings  /  POST /settings
# ---------------------------------------------------------------------------

@app.get("/settings")
async def get_settings():
    return {
        "provider": config.PROVIDER,
        "model": config.MODEL,
        "has_anthropic_key": bool(config.ANTHROPIC_API_KEY),
        "has_openrouter_key": bool(config.OPENROUTER_API_KEY),
        "default_mode": config.DEFAULT_MODE,
        "models": MODEL_CATALOGUE,
    }


@app.post("/settings")
async def update_settings(request: Request):
    body = await request.json()
    env_path = config.PACKAGE_ROOT / ".env"
    lines = [
        "# MBSE System Configuration",
        f"PROVIDER={body.get('provider', config.PROVIDER)}",
        f"MODEL={body.get('model', config.MODEL)}",
        f"DEFAULT_MODE={body.get('default_mode', config.DEFAULT_MODE)}",
        "",
    ]
    ak = body.get("anthropic_key", "").strip() or config.ANTHROPIC_API_KEY
    if ak:
        lines.append(f"ANTHROPIC_API_KEY={ak}")
    ork = body.get("openrouter_key", "").strip() or config.OPENROUTER_API_KEY
    if ork:
        lines.append(f"OPENROUTER_API_KEY={ork}")
    lines.append("")
    env_path.write_text("\n".join(lines), encoding="utf-8")
    _reload_config()
    return {
        "status": "ok",
        "provider": config.PROVIDER,
        "model": config.MODEL,
        "default_mode": config.DEFAULT_MODE,
    }


# ---------------------------------------------------------------------------
# GET /models
# ---------------------------------------------------------------------------

@app.get("/models")
async def list_models():
    return {"models": MODEL_CATALOGUE}


# ---------------------------------------------------------------------------
# GET /check-updates
# ---------------------------------------------------------------------------

@app.get("/check-updates")
async def check_updates():
    """Check if there are remote updates available."""
    import subprocess
    pkg_root = str(config.PACKAGE_ROOT)
    try:
        git_check = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if git_check.returncode != 0:
            return {"behind": 0, "available": False, "error": "Git is not installed"}

        is_repo = subprocess.run(
            ["git", "rev-parse", "--git-dir"], capture_output=True, text=True, cwd=pkg_root,
        )
        if is_repo.returncode != 0:
            return {
                "behind": 0,
                "available": False,
                "error": "Not a git repository. Was the project installed from a zip? Clone from GitHub to enable updates.",
            }

        remote = subprocess.run(
            ["git", "remote"], capture_output=True, text=True, cwd=pkg_root,
        )
        if not remote.stdout.strip():
            return {
                "behind": 0,
                "available": False,
                "error": "No git remote configured.",
            }

        fetch = subprocess.run(
            ["git", "fetch", "--quiet"], capture_output=True, text=True,
            cwd=pkg_root, timeout=15,
        )
        if fetch.returncode != 0:
            return {"behind": 0, "available": False, "error": "Could not reach GitHub. Check your network connection."}

        result = subprocess.run(
            ["git", "rev-list", "HEAD..@{u}", "--count"],
            capture_output=True, text=True, cwd=pkg_root, timeout=10,
        )
        if result.returncode != 0:
            return {
                "behind": 0,
                "available": False,
                "error": "No upstream branch set. Run: git branch --set-upstream-to=origin/main main",
            }

        behind = int(result.stdout.strip())

        commits = []
        if behind > 0:
            log = subprocess.run(
                ["git", "log", "HEAD..@{u}", "--pretty=format:%s"],
                capture_output=True, text=True, cwd=pkg_root, timeout=10,
            )
            if log.returncode == 0 and log.stdout.strip():
                commits = [line for line in log.stdout.strip().splitlines() if line.strip()]

        return {"behind": behind, "available": behind > 0, "commits": commits}
    except Exception as exc:
        return {"behind": 0, "available": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# POST /update
# ---------------------------------------------------------------------------

@app.post("/update")
async def update_software():
    """Pull latest from GitHub and reinstall."""
    import subprocess
    try:
        git_check = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if git_check.returncode != 0:
            return {"status": "error", "message": "Git is not installed. Download updates manually from GitHub."}

        pull = subprocess.run(
            ["git", "pull"], capture_output=True, text=True,
            cwd=str(config.PACKAGE_ROOT), timeout=30,
        )
        if pull.returncode != 0:
            return {"status": "error", "message": "Git pull failed: " + pull.stderr.strip()}

        if "Already up to date" in pull.stdout:
            return {"status": "ok", "message": "Already up to date.", "updated": False}

        install = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "-q"],
            capture_output=True, text=True,
            cwd=str(config.PACKAGE_ROOT), timeout=60,
        )

        changes = pull.stdout.strip()
        return {
            "status": "ok",
            "message": "Updated! Restart the server to apply changes.",
            "updated": True,
            "details": changes,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# GET /cost-history
# ---------------------------------------------------------------------------

@app.get("/cost-history")
async def cost_history():
    """Read output/cost_log.jsonl and return aggregated summary."""
    log_path = config.OUTPUT_DIR / "cost_log.jsonl"
    if not log_path.exists():
        return {"runs": [], "total_spend": 0.0, "avg_per_run": 0.0, "total_runs": 0}

    runs = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    total_spend = sum(r.get("totals", {}).get("cost_usd", 0.0) for r in runs)
    avg_per_run = (total_spend / len(runs)) if runs else 0.0

    return {
        "runs": runs,
        "total_runs": len(runs),
        "total_spend": round(total_spend, 6),
        "avg_per_run": round(avg_per_run, 6),
    }


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def start_server(port: int = 8000):
    """Start the web server."""
    import uvicorn
    print(f"\n  MBSE web interface starting...")
    print(f"  Open http://localhost:{port} in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
