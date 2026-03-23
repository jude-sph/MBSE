import json
from pathlib import Path
from src.project import load_project, save_project, new_project, backup_project, get_project_path


def test_get_project_path():
    path = get_project_path()
    assert path.name == "project.json"


def test_new_project_creates_empty():
    project = new_project("capella", "Test Project")
    assert project.project.name == "Test Project"
    assert project.meta.mode == "capella"
    assert len(project.batches) == 0
    assert len(project.requirements) == 0


def test_new_project_rhapsody():
    project = new_project("rhapsody", "Rhapsody Test")
    assert project.meta.mode == "rhapsody"
    assert project.instructions["tool"] == "IBM Rhapsody 10.0"


def test_save_and_load_round_trip(tmp_path):
    project = new_project("capella", "Round Trip Test")
    path = tmp_path / "project.json"
    save_project(project, path)
    assert path.exists()
    loaded = load_project(path)
    assert loaded.project.name == "Round Trip Test"
    assert loaded.meta.mode == "capella"


def test_load_nonexistent_returns_none(tmp_path):
    result = load_project(tmp_path / "nonexistent.json")
    assert result is None


def test_save_updates_last_modified(tmp_path):
    project = new_project("capella")
    path = tmp_path / "project.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.project.last_modified is not None


def test_backup_renames_file(tmp_path):
    project = new_project("capella", "Old Project")
    path = tmp_path / "project.json"
    save_project(project, path)
    backup_path = backup_project(path)
    assert backup_path is not None
    assert backup_path.exists()
    assert not path.exists()  # original was renamed
    backups = list(tmp_path.glob("project-backup-*.json"))
    assert len(backups) == 1


def test_backup_nonexistent_returns_none(tmp_path):
    result = backup_project(tmp_path / "nonexistent.json")
    assert result is None
