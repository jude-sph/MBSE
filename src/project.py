import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import CWD
from src.models import ProjectModel, ProjectMeta, Meta


def get_project_path() -> Path:
    return CWD / "project.json"


def new_project(mode: str, name: str = "Untitled Project") -> ProjectModel:
    return ProjectModel(
        project=ProjectMeta(name=name),
        batches=[],
        meta=Meta(
            source_file="project",
            mode=mode,
            selected_layers=[],
            llm_provider="openrouter",
            llm_model="",
        ),
        requirements=[],
        layers={},
        links=[],
        instructions={"tool": "Capella 7.0" if mode == "capella" else "IBM Rhapsody 10.0", "steps": []},
    )


def save_project(project: ProjectModel, path: Path | None = None) -> Path:
    path = path or get_project_path()
    project.project.last_modified = datetime.now(timezone.utc)
    data = json.loads(project.model_dump_json())
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def load_project(path: Path | None = None) -> ProjectModel | None:
    path = path or get_project_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectModel.model_validate(data)
    except Exception:
        return None


def backup_project(path: Path | None = None) -> Path | None:
    path = path or get_project_path()
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.parent / f"project-backup-{timestamp}.json"
    path.rename(backup_path)
    return backup_path
