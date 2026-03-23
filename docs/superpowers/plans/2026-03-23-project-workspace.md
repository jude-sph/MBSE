# Project Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the MBSE app from single-shot generation to a persistent project workspace where engineers process requirements in small batches that accumulate into a growing model.

**Architecture:** Add a `project.json` persistence layer, modify the LLM pipeline to accept existing model context, add batch history tracking, and update the UI to support the iterative "Add Batch" workflow. All changes are additive -- existing functionality is preserved.

**Tech Stack:** Same as existing (Python/FastAPI, Pydantic, vanilla JS). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-23-project-workspace-design.md`

---

## File Map

```
Changes to existing files:
├── src/models/core.py          # Add ProjectMeta, BatchRecord, ProjectModel
├── src/stages/generate.py      # Add existing_elements parameter + context formatting
├── src/stages/link.py          # Add existing_links parameter
├── src/pipeline.py             # Add existing_model parameter, merge logic, ID collision fix
├── src/web/app.py              # Project load/save, batch workflow endpoints
├── src/web/templates/index.html # Project name, Add Batch, batch history tab
├── src/web/static/app.js       # Project state, batch history rendering, mode lock
├── src/web/static/style.css    # Batch history styles, mode lock styles

New files:
├── src/project.py              # Project persistence: load/save/new/backup
├── tests/test_project.py       # Tests for project persistence
├── tests/test_pipeline_incremental.py  # Tests for context-aware pipeline
```

---

### Task 1: Project Data Model

**Files:**
- Modify: `src/models/core.py`
- Create: `tests/test_project_model.py`

- [ ] **Step 1: Write tests for new models**

```python
# tests/test_project_model.py
from src.models import ProjectMeta, BatchRecord, ProjectModel, MBSEModel, Meta, Requirement


def test_project_meta():
    pm = ProjectMeta(name="PIB Icebreaker")
    assert pm.name == "PIB Icebreaker"
    assert pm.created_at is not None


def test_batch_record():
    br = BatchRecord(
        id="batch-001",
        source_file="SAR-reqs.xlsx",
        requirement_ids=["REQ-001", "REQ-002"],
        layers_generated=["operational_analysis"],
        model="deepseek/deepseek-chat-v3-0324",
        cost=0.05,
    )
    assert br.id == "batch-001"
    assert len(br.requirement_ids) == 2


def test_project_model_round_trip():
    project = ProjectModel(
        project=ProjectMeta(name="Test"),
        batches=[],
        meta=Meta(source_file="project", mode="capella", selected_layers=[],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[],
        layers={},
        links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )
    json_str = project.model_dump_json()
    parsed = ProjectModel.model_validate_json(json_str)
    assert parsed.project.name == "Test"


def test_project_model_extends_mbse_model():
    """ProjectModel should be usable anywhere MBSEModel is."""
    project = ProjectModel(
        project=ProjectMeta(name="Test"),
        batches=[],
        meta=Meta(source_file="project", mode="capella", selected_layers=[],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[],
        layers={},
        links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )
    # Should have all MBSEModel fields
    assert hasattr(project, 'meta')
    assert hasattr(project, 'layers')
    assert hasattr(project, 'links')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_model.py -v`

- [ ] **Step 3: Add models to core.py**

Add to `src/models/core.py`:

```python
class ProjectMeta(BaseModel):
    name: str = "Untitled Project"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BatchRecord(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_file: str
    requirement_ids: list[str]
    layers_generated: list[str]
    model: str
    cost: float


class ProjectModel(MBSEModel):
    """Extends MBSEModel with project metadata and batch history."""
    project: ProjectMeta = Field(default_factory=ProjectMeta)
    batches: list[BatchRecord] = Field(default_factory=list)
```

Update `src/models/__init__.py` if needed to export the new classes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_model.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/models/core.py src/models/__init__.py tests/test_project_model.py
git commit -m "feat: add ProjectModel, ProjectMeta, and BatchRecord data models"
```

---

### Task 2: Project Persistence (load/save/new/backup)

**Files:**
- Create: `src/project.py`
- Create: `tests/test_project.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_project.py
import json
from pathlib import Path
from src.project import load_project, save_project, new_project, get_project_path
from src.models import ProjectModel, ProjectMeta, Meta


def test_get_project_path():
    path = get_project_path()
    assert path.name == "project.json"


def test_new_project_creates_empty():
    project = new_project("capella", "Test Project")
    assert project.project.name == "Test Project"
    assert project.meta.mode == "capella"
    assert len(project.batches) == 0
    assert len(project.requirements) == 0


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


def test_save_creates_backup_when_exists(tmp_path):
    project = new_project("capella", "Original")
    path = tmp_path / "project.json"
    save_project(project, path)

    # Save again -- should NOT create backup on normal save
    project.project.name = "Updated"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.project.name == "Updated"


def test_new_project_backup(tmp_path):
    """new_project with existing file should back up the old one."""
    project = new_project("capella", "Old Project")
    path = tmp_path / "project.json"
    save_project(project, path)

    # Create new project -- old one should be backed up
    from src.project import backup_project
    backup_project(path)
    backups = list(tmp_path.glob("project-backup-*.json"))
    assert len(backups) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Write project.py**

```python
# src/project.py
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_project.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/project.py tests/test_project.py
git commit -m "feat: add project persistence (load/save/new/backup)"
```

---

### Task 3: Context-Aware Generate Stage

**Files:**
- Modify: `src/stages/generate.py`
- Update: `tests/test_stages.py`

- [ ] **Step 1: Write tests**

Add to `tests/test_stages.py`:

```python
def test_generate_with_existing_elements(sample_requirements):
    """Generate should accept existing_elements context."""
    existing = {
        "entities": [{"id": "OE-001", "name": "PIB Icebreaker", "type": "OperationalEntity"}],
        "capabilities": [],
        "scenarios": [],
        "activities": [],
    }
    mock_response = {
        "entities": [
            {"id": "OE-005", "name": "Coast Guard HQ", "type": "OperationalEntity", "actors": []}
        ],
        "capabilities": [],
        "scenarios": [],
        "activities": [],
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("capella", "operational_analysis", sample_requirements, tracker,
                                existing_elements=existing)
    assert result["entities"][0]["id"] == "OE-005"


def test_generate_without_existing_elements_still_works(sample_requirements):
    """Backward compatible: no existing_elements = same as before."""
    mock_response = {"entities": [{"id": "OE-001", "name": "Test", "type": "OperationalEntity", "actors": []}],
                     "capabilities": [], "scenarios": [], "activities": []}
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("capella", "operational_analysis", sample_requirements, tracker)
    assert "entities" in result
```

- [ ] **Step 2: Modify generate.py**

Add `existing_elements` parameter to `generate_layer()`. When provided, format a compact summary and inject it into the prompt:

```python
def generate_layer(mode, layer_key, requirements, tracker, client=None, existing_elements=None):
    prompt_file = PROMPT_MAP.get((mode, layer_key))
    if not prompt_file:
        raise ValueError(f"No prompt template for mode={mode}, layer={layer_key}")
    template = (PROMPTS_DIR / prompt_file).read_text()
    reqs_json = json.dumps([r.model_dump() for r in requirements], indent=2)

    existing_ctx = ""
    if existing_elements:
        existing_ctx = _format_existing_elements(existing_elements)

    prompt = template.format(requirements=reqs_json, existing_elements=existing_ctx)
    return call_llm(...)


def _format_existing_elements(layer_data: dict) -> str:
    """Format existing layer elements as a compact summary for the prompt."""
    if not layer_data:
        return ""
    lines = ["Existing elements in this layer (DO NOT recreate these, reference by ID):"]
    for collection_key, elements in layer_data.items():
        if not isinstance(elements, list):
            continue
        for elem in elements:
            if isinstance(elem, dict):
                eid = elem.get("id", "?")
                name = elem.get("name", "?")
                etype = elem.get("type", collection_key)
                lines.append(f"- {eid}: {name} ({etype})")
    return "\n".join(lines) if len(lines) > 1 else ""
```

Also update all 10 prompt templates in `prompts/` to include the `{{existing_elements}}` placeholder. Add it near the top of each template, after the requirements section. If empty, it's invisible.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_stages.py -v`

- [ ] **Step 4: Commit**

```bash
git add src/stages/generate.py prompts/generate_*.txt tests/test_stages.py
git commit -m "feat: context-aware generate stage with existing_elements support"
```

---

### Task 4: Context-Aware Link Stage

**Files:**
- Modify: `src/stages/link.py`
- Modify: `prompts/link.txt`
- Update: `tests/test_stages.py`

- [ ] **Step 1: Write test**

```python
def test_link_with_existing_links(sample_requirements):
    """Link stage should accept existing links and only generate new ones."""
    elements = {"operational_analysis": {"activities": [{"id": "OA-005", "name": "New Activity"}]}}
    existing_links = [{"id": "LNK-001", "source": "OA-001", "target": "REQ-001", "type": "satisfies", "description": "existing"}]
    mock_response = {"links": [{"id": "LNK-010", "source": "OA-005", "target": "REQ-SAR-007", "type": "satisfies", "description": "new link"}]}
    tracker = CostTracker(model="test-model")
    with patch("src.stages.link.call_llm", return_value=mock_response):
        result = generate_links("capella", elements, sample_requirements, tracker, existing_links=existing_links)
    assert result["links"][0]["id"] == "LNK-010"
```

- [ ] **Step 2: Modify link.py**

Add `existing_links` parameter. Format existing links as context in the prompt. Update `prompts/link.txt` to include `{existing_links}` placeholder.

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```bash
git add src/stages/link.py prompts/link.txt tests/test_stages.py
git commit -m "feat: context-aware link stage with existing_links support"
```

---

### Task 5: Pipeline Merge Logic & ID Collision Fix

**Files:**
- Modify: `src/pipeline.py`
- Create: `tests/test_pipeline_incremental.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_pipeline_incremental.py
from src.pipeline import merge_batch_into_project, fix_id_collisions
from src.models import ProjectModel, ProjectMeta, Meta, Requirement, Link


def make_empty_project():
    return ProjectModel(
        project=ProjectMeta(name="Test"),
        batches=[],
        meta=Meta(source_file="project", mode="capella", selected_layers=[],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[],
        layers={},
        links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )


def test_merge_appends_requirements():
    project = make_empty_project()
    new_reqs = [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")]
    new_layers = {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Test"}]}}
    new_links = [Link(id="LNK-001", source="OE-001", target="REQ-001", type="satisfies", description="test")]
    merge_batch_into_project(project, new_reqs, new_layers, new_links, {"tool": "Capella 7.0", "steps": []},
                             source_file="test.xlsx", layers_generated=["operational_analysis"], model_name="test", cost=0.05)
    assert len(project.requirements) == 1
    assert "operational_analysis" in project.layers
    assert len(project.links) == 1
    assert len(project.batches) == 1


def test_merge_second_batch_accumulates():
    project = make_empty_project()
    # First batch
    merge_batch_into_project(project,
        [Requirement(id="REQ-001", text="First", source_dig="DIG-001")],
        {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Entity A"}]}},
        [], {"tool": "Capella 7.0", "steps": []},
        "batch1.xlsx", ["operational_analysis"], "test", 0.01)
    # Second batch
    merge_batch_into_project(project,
        [Requirement(id="REQ-002", text="Second", source_dig="DIG-002")],
        {"operational_analysis": {"entities": [{"id": "OE-002", "name": "Entity B"}]}},
        [], {"tool": "Capella 7.0", "steps": []},
        "batch2.xlsx", ["operational_analysis"], "test", 0.02)
    assert len(project.requirements) == 2
    assert len(project.layers["operational_analysis"]["entities"]) == 2
    assert len(project.batches) == 2


def test_fix_id_collisions():
    existing_ids = {"OE-001", "OE-002"}
    new_elements = [{"id": "OE-001", "name": "Duplicate"}, {"id": "OE-003", "name": "New"}]
    fixed = fix_id_collisions(new_elements, existing_ids)
    ids = {e["id"] for e in fixed}
    assert "OE-001" not in ids  # collision was renamed
    assert "OE-003" in ids      # no collision, unchanged
    assert len(ids) == 2
```

- [ ] **Step 2: Implement merge and ID collision logic in pipeline.py**

Add two new functions:

```python
def fix_id_collisions(new_elements: list[dict], existing_ids: set[str]) -> list[dict]:
    """Rename any new element IDs that collide with existing ones."""
    ...

def merge_batch_into_project(
    project: ProjectModel,
    new_requirements: list[Requirement],
    new_layers: dict,
    new_links: list[Link],
    new_instructions: dict,
    source_file: str,
    layers_generated: list[str],
    model_name: str,
    cost: float,
) -> None:
    """Merge a batch result into the project model. Mutates project in place."""
    ...
```

The merge logic:
1. Collect all existing element IDs across all layers
2. For each new layer's collections, run `fix_id_collisions`
3. Append new elements to existing layer collections (create layer if first time)
4. Append new requirements
5. Append new links (also fix link source/target IDs if they were renamed)
6. Replace instructions entirely
7. Create and append a BatchRecord
8. Update project.meta.last_modified

Also modify `run_pipeline()` to accept `existing_model: ProjectModel | None`. When provided:
- Pass `existing_elements=existing_model.layers.get(layer_key)` to `generate_layer()`
- Pass `existing_links=existing_model.links` to `generate_links()`
- Pass the full accumulated model to `generate_instructions()`

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_pipeline_incremental.py -v`

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v` (ensure nothing is broken)

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline_incremental.py
git commit -m "feat: add batch merge logic with ID collision fix and context-aware pipeline"
```

---

### Task 6: Backend Endpoints (Project + Batch Workflow)

**Files:**
- Modify: `src/web/app.py`

- [ ] **Step 1: Add project endpoints and modify existing ones**

New/modified endpoints:

```
GET  /project              → Load current project (or null if none)
POST /project/new          → Create new project (backup old one if exists). Body: {name, mode}
POST /project/rename       → Rename project. Body: {name}
POST /run                  → Modified: now merges into project instead of creating standalone model
GET  /project/batches      → Return batch history
```

Key changes to `app.py`:

1. On app startup, load project from disk:
```python
from src.project import load_project, save_project, new_project, backup_project, get_project_path

current_project: ProjectModel | None = load_project()
```

2. `GET /project` returns `current_project.model_dump()` or `{"project": null}`

3. `POST /project/new`: backs up old project, creates fresh one, saves to disk

4. `POST /run` (modified): After pipeline returns an MBSEModel, call `merge_batch_into_project()` to merge into `current_project`. Save project to disk. Return the full project model.

5. The `_run_job_async` function: pass `existing_model=current_project` to `run_pipeline()`. After pipeline completes, merge and save.

6. `POST /job/{id}/edit` and `/job/{id}/chat`: After modifying the model, also save project to disk.

7. `GET /project/batches`: Return `current_project.batches` as JSON.

- [ ] **Step 2: Commit**

```bash
git add src/web/app.py
git commit -m "feat: add project endpoints and batch workflow to backend"
```

---

### Task 7: Frontend -- Project State & Batch Workflow

**Files:**
- Modify: `src/web/templates/index.html`
- Modify: `src/web/static/app.js`
- Modify: `src/web/static/style.css`

- [ ] **Step 1: Update HTML template**

In the top bar, add:
- Project name (editable span, id="project-name")
- Last modified text (id="project-modified")
- "New Project" button (id="btn-new-project")

Add a Batches tab button in the tab bar (after Raw JSON).

Add a `#tab-batches` pane div.

- [ ] **Step 2: Update app.js**

**On DOMContentLoaded:**
- Fetch `GET /project` to load current project
- If project exists: set `currentModel`, render tree, show project name, lock mode toggle if batches exist
- If no project: show empty state

**Rename "Generate Model" to "Add Batch"** in the button text.

**`proceedGenerate()` changes:**
- If no project exists yet, POST to `/project/new` first with current mode
- Then POST to `/run` as before
- On completion: fetch `/project` to get full merged model, render tree

**Mode lock:**
- If `currentModel.batches.length > 0`: disable mode toggle, add tooltip

**New Project button:**
- Confirm dialog ("This will archive the current project. Continue?")
- POST to `/project/new` with name from prompt and selected mode
- Reset UI to empty state

**Batch history tab (`renderBatchesTab()`):**
- Fetch `/project/batches`
- Render each batch as a card: timestamp, source file, requirement count, layers, model, cost
- Newest first

**Update `renderCoverageIndicator()`** -- no changes needed, already works on accumulated data.

**Remove localStorage persistence** -- replaced by server-side project.json. Remove `localStorage.setItem('mbse_currentModel', ...)` calls and the restore-on-load logic.

- [ ] **Step 3: Update style.css**

Add styles for:
- `.project-name` (editable, inline, font-weight bold)
- `.project-modified` (muted timestamp)
- `.btn-new-project` (same style as update button)
- `.mode-toggle.locked` (opacity 0.5, cursor not-allowed, tooltip)
- `.batch-card` (dark card with border, padding, flex layout)
- `.batch-meta` (timestamp, source file in muted text)
- `.batch-stats` (requirement count, layers, cost badges)
- `.empty-state` (centered message for no-project state)

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html src/web/static/app.js src/web/static/style.css
git commit -m "feat: add project workspace UI with batch history and mode lock"
```

---

### Task 8: Integration Test & Push

**Files:**
- Modify: `src/stages/__init__.py` (if needed for new exports)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Verify server starts**

Run: `mbsegen --web --port 8222` (different port to avoid conflicts)
Verify: Page loads, empty state shown (no project.json yet).

- [ ] **Step 3: Manual smoke test**

1. Open app -- should show "No project yet" empty state
2. Upload a small requirements file (3 requirements)
3. Select mode and 1 layer, click "Add Batch"
4. Should create project, run pipeline, show results
5. Upload a second file (different requirements)
6. Click "Add Batch" again -- model should grow, not replace
7. Check Batches tab -- should show 2 batches
8. Check coverage indicator -- should reflect all requirements
9. Refresh browser -- project should persist (loaded from project.json)
10. Click "New Project" -- should confirm, back up, and reset

- [ ] **Step 4: Commit any fixes**

- [ ] **Step 5: Push to GitHub**

```bash
git push
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Project data model | src/models/core.py |
| 2 | Project persistence | src/project.py |
| 3 | Context-aware generate | src/stages/generate.py, prompts/ |
| 4 | Context-aware link | src/stages/link.py, prompts/link.txt |
| 5 | Pipeline merge + ID fix | src/pipeline.py |
| 6 | Backend endpoints | src/web/app.py |
| 7 | Frontend UI | index.html, app.js, style.css |
| 8 | Integration + push | Tests, smoke test, git push |
