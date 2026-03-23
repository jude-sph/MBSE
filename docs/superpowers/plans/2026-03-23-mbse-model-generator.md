# MBSE Model Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that transforms pre-decomposed requirements into MBSE model structures for Capella (Arcadia) and IBM Rhapsody (SysML), following the reqdecomp project patterns.

**Architecture:** Python/FastAPI backend with vanilla JS frontend. A 5-stage LLM pipeline (Analyze → Clarify → Generate → Link → Instruct) produces a structured JSON model rendered as an interactive tree. Inline editing handles small changes; a chat agent with tools handles structural changes. Three LLM providers: Anthropic, OpenRouter, Local (Ollama).

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic 2.0+, openpyxl, httpx, anthropic SDK, openai SDK, vanilla JS, Jinja2

**Spec:** `docs/superpowers/specs/2026-03-23-mbse-model-generator-design.md`

**Reference project:** `/Users/jude/Documents/projects/Requirements` (reqdecomp app -- follow its patterns for config, LLM client, cost tracking, web server, update mechanism, and styling)

---

## File Map

```
MBSE/
├── pyproject.toml                    # Package metadata, deps, CLI entry point
├── requirements.txt                  # Plain dependency list
├── .env.example                      # Template for .env config
├── .gitignore                        # Already exists
├── pytest.ini                        # Test config
├── src/
│   ├── __init__.py
│   ├── main.py                       # CLI: argparse, --web, --setup
│   ├── config.py                     # Paths, env vars, MODEL_PRICING, MODEL_CATALOGUE
│   ├── llm_client.py                 # Unified LLM client (Anthropic/OpenRouter/Local)
│   ├── cost_tracker.py               # Token/cost accounting + JSONL logging
│   ├── parser.py                     # XLSX/CSV → list[Requirement]
│   ├── pipeline.py                   # Orchestrates 5 stages, emits SSE events
│   ├── exporter.py                   # JSON/XLSX/Text export
│   ├── models/
│   │   ├── __init__.py               # Re-exports all model classes
│   │   ├── core.py                   # MBSEModel, Meta, Requirement, Link, InstructionStep, CostEntry, CostSummary
│   │   ├── capella.py                # Arcadia: OA/SA/LA/PA element + layer models
│   │   └── rhapsody.py               # SysML: Req/BDD/IBD/Act/Seq/STM element + layer models
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── analyze.py                # Stage 1: parse + ambiguity detection
│   │   ├── clarify.py                # Stage 2: structured Q&A (conditional)
│   │   ├── generate.py               # Stage 3: layer-by-layer model generation
│   │   ├── link.py                   # Stage 4: cross-element relationships
│   │   └── instruct.py               # Stage 5: tool-specific recreation steps
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── tools.py                  # Tool definitions: add/modify/remove elements & links
│   │   └── chat.py                   # Chat agent orchestration via OpenRouter
│   └── web/
│       ├── app.py                    # FastAPI endpoints, SSE, update mechanism
│       ├── templates/
│       │   └── index.html            # Jinja2 main page
│       └── static/
│           ├── app.js                # All frontend interactivity
│           └── style.css             # Dark theme styling
├── prompts/
│   ├── analyze.txt                   # Stage 1 prompt
│   ├── clarify.txt                   # Stage 2 prompt
│   ├── generate_capella_oa.txt       # Stage 3: Capella Operational Analysis
│   ├── generate_capella_sa.txt       # Stage 3: Capella System Analysis
│   ├── generate_capella_la.txt       # Stage 3: Capella Logical Architecture
│   ├── generate_capella_pa.txt       # Stage 3: Capella Physical Architecture
│   ├── generate_rhapsody_req.txt     # Stage 3: Rhapsody Requirements Diagram
│   ├── generate_rhapsody_bdd.txt     # Stage 3: Rhapsody Block Definition
│   ├── generate_rhapsody_ibd.txt     # Stage 3: Rhapsody Internal Block
│   ├── generate_rhapsody_act.txt     # Stage 3: Rhapsody Activity Diagram
│   ├── generate_rhapsody_seq.txt     # Stage 3: Rhapsody Sequence Diagram
│   ├── generate_rhapsody_stm.txt     # Stage 3: Rhapsody State Machine
│   ├── link.txt                      # Stage 4 prompt
│   ├── instruct_capella.txt          # Stage 5: Capella instructions
│   ├── instruct_rhapsody.txt         # Stage 5: Rhapsody instructions
│   └── agent_system.txt              # Chat agent system prompt
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Shared fixtures (sample requirements, mock LLM)
    ├── test_config.py
    ├── test_models.py
    ├── test_parser.py
    ├── test_cost_tracker.py
    ├── test_llm_client.py
    ├── test_stages.py
    ├── test_pipeline.py
    ├── test_agent_tools.py
    └── test_exporter.py
```

---

### Task 1: Project Scaffolding & Package Setup

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `pytest.ini`
- Create: `src/__init__.py`
- Create: `src/models/__init__.py`
- Create: `src/stages/__init__.py`
- Create: `src/agent/__init__.py`
- Create: `src/web/__init__.py` (empty, needed for package)
- Update: `.gitignore` (add `*.egg-info/`, `output/`, `.env`)

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mbsegen"
version = "0.1.0"
description = "Transform decomposed requirements into MBSE model structures for Capella and IBM Rhapsody"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Jude"},
]
dependencies = [
    "anthropic>=0.40.0",
    "openai>=1.50.0",
    "openpyxl>=3.1.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "python-multipart>=0.0.5",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
]

[project.scripts]
mbsegen = "src.main:main"

[project.urls]
Repository = "https://github.com/jude-sph/MBSE"

[tool.setuptools.packages.find]
include = ["src*"]

[tool.setuptools.package-data]
"*" = ["*.txt", "*.html", "*.css", "*.js"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create requirements.txt**

```
anthropic>=0.40.0
openai>=1.50.0
openpyxl>=3.1.0
pydantic>=2.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
fastapi>=0.115.0
uvicorn>=0.32.0
python-multipart>=0.0.5
jinja2>=3.1.0
```

- [ ] **Step 3: Create .env.example**

```env
# Provider: "anthropic", "openrouter", or "local"
PROVIDER=openrouter

# Anthropic direct
ANTHROPIC_API_KEY=sk-ant-...

# OpenRouter (set PROVIDER=openrouter to use)
OPENROUTER_API_KEY=sk-or-...

# Local LLM endpoint (set PROVIDER=local to use)
LOCAL_LLM_URL=http://localhost:11434/v1

# Model (works with all providers)
MODEL=anthropic/claude-sonnet-4

# Default output mode: "capella" or "rhapsody"
DEFAULT_MODE=capella
```

- [ ] **Step 4: Create pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 5: Create empty __init__.py files for all packages**

Create empty `__init__.py` in: `src/`, `src/models/`, `src/stages/`, `src/agent/`, `src/web/`, `tests/`

- [ ] **Step 6: Create prompts/ directory with empty placeholder files**

Create the `prompts/` directory with empty `.txt` files for all 16 prompt templates listed in the file map. These will be populated in later tasks.

- [ ] **Step 7: Verify package installs**

Run: `pip install -e ".[dev]"`
Expected: Successful installation with `mbsegen` CLI entry point registered.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml requirements.txt .env.example pytest.ini .gitignore src/ tests/ prompts/
git commit -m "feat: project scaffolding and package setup"
```

---

### Task 2: Configuration & Model Catalogue

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Reference:** Copy the pattern from `/Users/jude/Documents/projects/Requirements/src/config.py` -- same `MODEL_PRICING` dict and `MODEL_CATALOGUE` list, adapted for this project.

- [ ] **Step 1: Write test for config loading**

```python
# tests/test_config.py
from src import config


def test_model_pricing_has_entries():
    assert len(config.MODEL_PRICING) >= 14


def test_model_catalogue_has_entries():
    assert len(config.MODEL_CATALOGUE) >= 14


def test_each_catalogue_entry_has_required_fields():
    required = {"id", "name", "provider", "price", "quality", "speed", "description", "pros", "cons"}
    for model in config.MODEL_CATALOGUE:
        missing = required - set(model.keys())
        assert not missing, f"Model {model.get('id', '?')} missing fields: {missing}"


def test_catalogue_ids_match_pricing():
    pricing_ids = set(config.MODEL_PRICING.keys())
    catalogue_ids = {m["id"] for m in config.MODEL_CATALOGUE}
    assert catalogue_ids.issubset(pricing_ids), f"Catalogue models missing from pricing: {catalogue_ids - pricing_ids}"


def test_provider_defaults():
    assert config.PROVIDER in ("anthropic", "openrouter", "local")


def test_default_mode():
    assert config.DEFAULT_MODE in ("capella", "rhapsody")


def test_package_root_is_project_root():
    assert (config.PACKAGE_ROOT / "pyproject.toml").exists()


def test_prompts_dir_exists():
    assert config.PROMPTS_DIR.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL -- `src.config` module does not exist yet.

- [ ] **Step 3: Write config.py**

Create `src/config.py` with:
- `load_dotenv` loading `.env` from CWD then package root
- `PACKAGE_ROOT`, `PROMPTS_DIR`, `CWD` path constants
- `OUTPUT_DIR = CWD / "output"`
- `PROVIDER`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `LOCAL_LLM_URL`, `MODEL`, `DEFAULT_MODE` from env
- `MODEL_PRICING` dict -- copy all 14 entries from reqdecomp's `config.py` (lines 32-50)
- `MODEL_CATALOGUE` list -- copy all 14 entries from reqdecomp's `config.py` (lines 53-166), updating descriptions to reference MBSE model generation instead of requirements decomposition
- `CAPELLA_LAYERS` dict mapping layer keys to display names:
  ```python
  CAPELLA_LAYERS = {
      "operational_analysis": "Operational Analysis (OA)",
      "system_analysis": "System Analysis (SA)",
      "logical_architecture": "Logical Architecture (LA)",
      "physical_architecture": "Physical Architecture (PA)",
  }
  ```
- `RHAPSODY_DIAGRAMS` dict mapping diagram keys to display names:
  ```python
  RHAPSODY_DIAGRAMS = {
      "requirements_diagram": "Requirements Diagram",
      "block_definition": "Block Definition Diagram (BDD)",
      "internal_block": "Internal Block Diagram (IBD)",
      "activity_diagram": "Activity Diagram",
      "sequence_diagram": "Sequence Diagram",
      "state_machine": "State Machine Diagram",
  }
  ```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add configuration with model catalogue and pricing"
```

---

### Task 3: Pydantic Data Models

**Files:**
- Create: `src/models/core.py`
- Create: `src/models/capella.py`
- Create: `src/models/rhapsody.py`
- Update: `src/models/__init__.py` (re-export all models)
- Create: `tests/test_models.py`

**Reference:** See spec sections "Core Data Model", "Capella/Arcadia Element Types", "Rhapsody/SysML Element Types" for exact field definitions.

- [ ] **Step 1: Write tests for core models**

```python
# tests/test_models.py
import json
from src.models import (
    MBSEModel, Meta, Requirement, Link, InstructionStep,
    CostEntry, CostSummary,
)


def test_requirement_serialization():
    req = Requirement(id="REQ-SAR-001", text="The crew shall monitor GMDSS", source_dig="DIG-5967")
    data = req.model_dump()
    assert data["id"] == "REQ-SAR-001"
    assert data["source_dig"] == "DIG-5967"


def test_link_serialization():
    link = Link(id="LNK-001", source="OA-003", target="REQ-SAR-004", type="satisfies", description="test")
    data = link.model_dump()
    assert data["type"] == "satisfies"


def test_cost_summary_computed_fields():
    entries = [
        CostEntry(call_type="analyze", stage="analyze", input_tokens=1000, output_tokens=500, cost_usd=0.01),
        CostEntry(call_type="generate", stage="generate", input_tokens=2000, output_tokens=1000, cost_usd=0.02),
    ]
    summary = CostSummary(breakdown=entries)
    assert summary.total_input_tokens == 3000
    assert summary.total_output_tokens == 1500
    assert summary.total_cost_usd == 0.03
    assert summary.api_calls == 2


def test_meta_serialization():
    meta = Meta(
        source_file="test.xlsx", mode="capella",
        selected_layers=["operational_analysis"],
        llm_provider="openrouter", llm_model="anthropic/claude-sonnet-4",
    )
    data = meta.model_dump()
    assert data["mode"] == "capella"
    assert "operational_analysis" in data["selected_layers"]


def test_mbse_model_round_trip():
    model = MBSEModel(
        meta=Meta(source_file="test.xlsx", mode="capella", selected_layers=["operational_analysis"],
                  llm_provider="openrouter", llm_model="test-model"),
        requirements=[Requirement(id="REQ-001", text="Test requirement", source_dig="DIG-001")],
        layers={},
        links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )
    json_str = model.model_dump_json()
    parsed = MBSEModel.model_validate_json(json_str)
    assert parsed.meta.source_file == "test.xlsx"
    assert len(parsed.requirements) == 1


def test_instruction_step():
    step = InstructionStep(step=1, action="Create project", detail="File > New", layer="general")
    assert step.step == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL -- models don't exist yet.

- [ ] **Step 3: Write core.py**

Create `src/models/core.py` with Pydantic v2 models:
- `CostEntry(BaseModel)`: call_type, stage, input_tokens, output_tokens, cost_usd
- `CostSummary(BaseModel)`: breakdown (list[CostEntry]), computed properties: total_input_tokens, total_output_tokens, total_cost_usd, api_calls
- `Requirement(BaseModel)`: id, text, source_dig
- `Link(BaseModel)`: id, source, target, type, description
- `InstructionStep(BaseModel)`: step (int), action, detail, layer
- `Meta(BaseModel)`: source_file, mode (Literal["capella", "rhapsody"]), selected_layers (list[str]), generated_at (datetime, default_factory=now), llm_provider, llm_model, cost (CostSummary | None)
- `MBSEModel(BaseModel)`: meta, requirements (list[Requirement]), layers (dict[str, Any]), links (list[Link]), instructions (dict with "tool" and "steps")

- [ ] **Step 4: Write capella.py**

Create `src/models/capella.py` with Pydantic models for each Arcadia layer:
- OA: `OperationalEntity`, `OperationalCapability`, `Scenario`, `ScenarioStep`, `OperationalActivity`, `OperationalAnalysisLayer`
- SA: `SystemFunction`, `SystemFunctionalExchange`, `SystemAnalysisLayer`
- LA: `LogicalComponent`, `LogicalFunction`, `LogicalArchitectureLayer`
- PA: `PhysicalComponent`, `PhysicalFunction`, `PhysicalLink`, `PhysicalArchitectureLayer`

Each element model has an `id` (str), `name` (str), and type-specific fields matching the spec.

- [ ] **Step 5: Write rhapsody.py**

Create `src/models/rhapsody.py` with Pydantic models for each SysML diagram type:
- `SysMLRequirement`, `RequirementsDiagramLayer`
- `Block`, `BlockDefinitionLayer`
- `IBDPart`, `IBDConnector`, `InternalBlockLayer`
- `SysMLAction`, `ActivityDiagramLayer`
- `Lifeline`, `SequenceMessage`, `SequenceDiagramLayer`
- `SMState`, `SMTransition`, `StateMachineLayer`

- [ ] **Step 6: Update models/__init__.py to re-export all models**

```python
from src.models.core import *
from src.models.capella import *
from src.models.rhapsody import *
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add src/models/ tests/test_models.py
git commit -m "feat: add Pydantic data models for MBSE, Capella, and Rhapsody"
```

---

### Task 4: Cost Tracker & LLM Client

**Files:**
- Create: `src/cost_tracker.py`
- Create: `src/llm_client.py`
- Create: `tests/test_cost_tracker.py`
- Create: `tests/test_llm_client.py`

**Reference:** Copy patterns directly from reqdecomp:
- `/Users/jude/Documents/projects/Requirements/src/cost_tracker.py`
- `/Users/jude/Documents/projects/Requirements/src/llm_client.py`

- [ ] **Step 1: Write cost tracker tests**

```python
# tests/test_cost_tracker.py
import json
from pathlib import Path
from src.cost_tracker import CostTracker


def test_record_and_summary():
    tracker = CostTracker(model="anthropic/claude-sonnet-4")
    tracker.record(call_type="analyze", stage="analyze", input_tokens=1000, output_tokens=500)
    summary = tracker.get_summary()
    assert summary.api_calls == 1
    assert summary.total_input_tokens == 1000
    assert summary.total_cost_usd > 0


def test_actual_cost_overrides_estimate():
    tracker = CostTracker(model="anthropic/claude-sonnet-4")
    tracker.record(call_type="analyze", stage="analyze", input_tokens=1000, output_tokens=500, actual_cost=0.99)
    summary = tracker.get_summary()
    assert summary.total_cost_usd == 0.99


def test_format_cost_line():
    tracker = CostTracker(model="anthropic/claude-sonnet-4")
    tracker.record(call_type="test", stage="test", input_tokens=100, output_tokens=50)
    line = tracker.format_cost_line()
    assert "1 API call" in line
    assert "$" in line


def test_cost_log_append(tmp_path):
    log_path = tmp_path / "cost_log.jsonl"
    tracker = CostTracker(model="test-model", cost_log_path=log_path)
    tracker.record(call_type="test", stage="test", input_tokens=100, output_tokens=50)
    tracker.flush_log(run_type="pipeline_run", source_file="test.xlsx", mode="capella", layers=["operational_analysis"])
    assert log_path.exists()
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["type"] == "pipeline_run"
    assert entry["source_file"] == "test.xlsx"


def test_reset_clears_entries():
    tracker = CostTracker(model="test-model")
    tracker.record(call_type="test", stage="test", input_tokens=100, output_tokens=50)
    tracker.reset()
    assert tracker.get_summary().api_calls == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_tracker.py -v`
Expected: FAIL.

- [ ] **Step 3: Write cost_tracker.py**

Adapt from reqdecomp's `cost_tracker.py`. Add:
- `cost_log_path` parameter (Path) for the JSONL log file location
- `flush_log(run_type, source_file, mode, layers)` method that appends a JSON line to the cost log with timestamp, run metadata, per-stage breakdown, and totals
- Same `record()`, `get_summary()`, `format_cost_line()`, `reset()` methods

- [ ] **Step 4: Run cost tracker tests**

Run: `pytest tests/test_cost_tracker.py -v`
Expected: All PASS.

- [ ] **Step 5: Write LLM client tests**

```python
# tests/test_llm_client.py
from src.llm_client import _extract_json


def test_extract_json_from_code_block():
    text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_plain():
    text = '{"key": "value"}'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_from_generic_code_block():
    text = '```\n{"key": "value"}\n```'
    assert _extract_json(text) == '{"key": "value"}'
```

- [ ] **Step 6: Write llm_client.py**

Copy from reqdecomp's `llm_client.py` and extend:
- Add `"local"` provider support in `_create_client()`: uses `openai.OpenAI(api_key="not-needed", base_url=LOCAL_LLM_URL)` where `LOCAL_LLM_URL` comes from config
- Add `call_llm_with_tools()` function for the chat agent -- uses `client.chat.completions.create()` with `tools=` parameter. Only works with Anthropic/OpenRouter providers.
- Keep same retry logic, JSON extraction, cost tracking interface

- [ ] **Step 7: Run all tests**

Run: `pytest tests/test_cost_tracker.py tests/test_llm_client.py -v`
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add src/cost_tracker.py src/llm_client.py tests/test_cost_tracker.py tests/test_llm_client.py
git commit -m "feat: add cost tracker with JSONL logging and unified LLM client"
```

---

### Task 5: File Parser (XLSX/CSV)

**Files:**
- Create: `src/parser.py`
- Create: `tests/test_parser.py`
- Create: `tests/fixtures/sample_requirements.xlsx` (small test file)
- Create: `tests/fixtures/sample_requirements.csv`

- [ ] **Step 1: Write parser tests**

```python
# tests/test_parser.py
from pathlib import Path
from src.parser import parse_requirements_file
from src.models import Requirement

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_xlsx():
    reqs = parse_requirements_file(FIXTURES / "sample_requirements.xlsx")
    assert len(reqs) >= 1
    assert all(isinstance(r, Requirement) for r in reqs)
    assert all(r.id and r.text for r in reqs)


def test_parse_csv():
    reqs = parse_requirements_file(FIXTURES / "sample_requirements.csv")
    assert len(reqs) >= 1
    assert all(isinstance(r, Requirement) for r in reqs)


def test_parse_unknown_format_raises():
    import pytest
    with pytest.raises(ValueError, match="Unsupported"):
        parse_requirements_file(Path("test.doc"))
```

- [ ] **Step 2: Create test fixtures**

Create `tests/fixtures/sample_requirements.xlsx` -- a small Excel file with columns: `id`, `text`, `source_dig`. Include 3 sample SAR requirements from the spec (REQ-SAR-001, REQ-SAR-004, REQ-SAR-007).

Create `tests/fixtures/sample_requirements.csv` -- same data as CSV.

- [ ] **Step 3: Write parser.py**

```python
# src/parser.py
from pathlib import Path
from src.models import Requirement


def parse_requirements_file(file_path: Path) -> list[Requirement]:
    """Parse XLSX or CSV file into a list of Requirement objects."""
    suffix = file_path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return _parse_xlsx(file_path)
    elif suffix == ".csv":
        return _parse_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .xlsx, .xls, or .csv")
```

Implement `_parse_xlsx()` using openpyxl: read first sheet, auto-detect header row by looking for columns named `id`/`text`/`source_dig` (case-insensitive), iterate rows and create `Requirement` objects.

Implement `_parse_csv()` using `csv.DictReader`: same column detection logic.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py tests/fixtures/
git commit -m "feat: add XLSX/CSV requirement file parser"
```

---

### Task 6: Pipeline Stages 1-2 (Analyze & Clarify)

**Files:**
- Create: `src/stages/analyze.py`
- Create: `src/stages/clarify.py`
- Write: `prompts/analyze.txt`
- Write: `prompts/clarify.txt`
- Create: `tests/test_stages.py`
- Create: `tests/conftest.py` (shared fixtures)

- [ ] **Step 1: Create shared test fixtures**

```python
# tests/conftest.py
import pytest
from src.models import Requirement


@pytest.fixture
def sample_requirements():
    return [
        Requirement(id="REQ-SAR-001", text="The crew shall monitor GMDSS frequencies (VHF Ch 16/70, MF 2182 kHz).", source_dig="DIG-5967"),
        Requirement(id="REQ-SAR-004", text="The vessel shall maintain station within a 10-meter radius of a fixed geographical position for short durations.", source_dig="DIG-5967"),
        Requirement(id="REQ-SAR-007", text="The vessel shall support the safe launch and recovery of the Fast Rescue Craft (FRC) from the davit.", source_dig="DIG-5967"),
    ]
```

- [ ] **Step 2: Write tests for analyze stage**

```python
# tests/test_stages.py (start with analyze tests)
import json
from unittest.mock import patch, MagicMock
from src.stages.analyze import analyze_requirements
from src.cost_tracker import CostTracker


def test_analyze_returns_flagged_requirements(sample_requirements):
    mock_response = {
        "flagged": [
            {"id": "REQ-SAR-004", "issue": "What does 'short durations' mean?", "suggestion": "Define specific time range (e.g., 30 minutes)"}
        ],
        "clear": ["REQ-SAR-001", "REQ-SAR-007"]
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.analyze.call_llm", return_value=mock_response):
        result = analyze_requirements(sample_requirements, tracker)
    assert "flagged" in result
    assert len(result["flagged"]) == 1
    assert result["flagged"][0]["id"] == "REQ-SAR-004"


def test_analyze_returns_empty_flagged_when_all_clear(sample_requirements):
    mock_response = {"flagged": [], "clear": ["REQ-SAR-001", "REQ-SAR-004", "REQ-SAR-007"]}
    tracker = CostTracker(model="test-model")
    with patch("src.stages.analyze.call_llm", return_value=mock_response):
        result = analyze_requirements(sample_requirements, tracker)
    assert len(result["flagged"]) == 0
```

- [ ] **Step 3: Write the analyze.txt prompt template**

Create `prompts/analyze.txt`. The prompt should:
- Accept requirements as a JSON array
- Ask the LLM to identify ambiguous, incomplete, or vague requirements
- Return JSON with `flagged` (array of {id, issue, suggestion}) and `clear` (array of ids)
- Include an example of what "ambiguous" means in the MBSE context

- [ ] **Step 4: Write analyze.py**

```python
# src/stages/analyze.py
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm
from src.models import Requirement


def analyze_requirements(requirements: list[Requirement], tracker: CostTracker, client=None) -> dict:
    """Stage 1: Analyze requirements for ambiguity. Returns {flagged: [...], clear: [...]}."""
    template = (PROMPTS_DIR / "analyze.txt").read_text()
    reqs_json = [r.model_dump() for r in requirements]
    prompt = template.format(requirements=reqs_json)
    return call_llm(prompt=prompt, cost_tracker=tracker, call_type="analyze", stage="analyze", client=client)
```

- [ ] **Step 5: Write clarify.py**

```python
# src/stages/clarify.py
from src.models import Requirement


def apply_clarifications(requirements: list[Requirement], clarifications: dict[str, str]) -> list[Requirement]:
    """Stage 2: Apply user clarification responses to requirements.

    clarifications: dict mapping requirement ID to user's clarification text.
    Returns updated requirements list with clarifications appended to text.
    """
    updated = []
    for req in requirements:
        if req.id in clarifications:
            updated.append(req.model_copy(update={
                "text": f"{req.text} [Clarification: {clarifications[req.id]}]"
            }))
        else:
            updated.append(req)
    return updated
```

- [ ] **Step 6: Write clarify.txt prompt template**

The clarify prompt is used only if the user asks the LLM to suggest clarification wording. It's a simpler prompt that takes a requirement + user clarification and returns a refined requirement statement.

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_stages.py -v`
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add src/stages/analyze.py src/stages/clarify.py prompts/analyze.txt prompts/clarify.txt tests/test_stages.py tests/conftest.py
git commit -m "feat: add pipeline stages 1-2 (analyze and clarify)"
```

---

### Task 7: Pipeline Stage 3 (Generate)

**Files:**
- Create: `src/stages/generate.py`
- Write: `prompts/generate_capella_oa.txt`
- Write: `prompts/generate_capella_sa.txt`
- Write: `prompts/generate_capella_la.txt`
- Write: `prompts/generate_capella_pa.txt`
- Write: `prompts/generate_rhapsody_req.txt`
- Write: `prompts/generate_rhapsody_bdd.txt`
- Write: `prompts/generate_rhapsody_ibd.txt`
- Write: `prompts/generate_rhapsody_act.txt`
- Write: `prompts/generate_rhapsody_seq.txt`
- Write: `prompts/generate_rhapsody_stm.txt`
- Update: `tests/test_stages.py`

This is the largest task. The generate stage dispatches one LLM call per selected layer/diagram.

- [ ] **Step 1: Write generate tests**

Add to `tests/test_stages.py`:

```python
from unittest.mock import patch
from src.stages.generate import generate_layer
from src.cost_tracker import CostTracker


def test_generate_capella_oa_returns_valid_structure(sample_requirements):
    mock_response = {
        "entities": [
            {"id": "OE-001", "name": "PIB Icebreaker", "type": "OperationalEntity", "actors": ["PIB Commanding Officer"]}
        ],
        "capabilities": [
            {"id": "OC-001", "name": "Conduct SAR", "involved_entities": ["OE-001"]}
        ],
        "scenarios": [],
        "activities": []
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("capella", "operational_analysis", sample_requirements, tracker)
    assert "entities" in result
    assert result["entities"][0]["name"] == "PIB Icebreaker"


def test_generate_rhapsody_bdd_returns_valid_structure(sample_requirements):
    mock_response = {
        "blocks": [
            {"id": "BDD-001", "name": "PIB Icebreaker", "type": "Block", "properties": [], "ports": []}
        ]
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("rhapsody", "block_definition", sample_requirements, tracker)
    assert "blocks" in result
```

- [ ] **Step 2: Write generate.py**

```python
# src/stages/generate.py
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm
from src.models import Requirement

# Maps (mode, layer_key) to prompt template filename
PROMPT_MAP = {
    ("capella", "operational_analysis"): "generate_capella_oa.txt",
    ("capella", "system_analysis"): "generate_capella_sa.txt",
    ("capella", "logical_architecture"): "generate_capella_la.txt",
    ("capella", "physical_architecture"): "generate_capella_pa.txt",
    ("rhapsody", "requirements_diagram"): "generate_rhapsody_req.txt",
    ("rhapsody", "block_definition"): "generate_rhapsody_bdd.txt",
    ("rhapsody", "internal_block"): "generate_rhapsody_ibd.txt",
    ("rhapsody", "activity_diagram"): "generate_rhapsody_act.txt",
    ("rhapsody", "sequence_diagram"): "generate_rhapsody_seq.txt",
    ("rhapsody", "state_machine"): "generate_rhapsody_stm.txt",
}


def generate_layer(
    mode: str, layer_key: str, requirements: list[Requirement],
    tracker: CostTracker, client=None
) -> dict:
    """Stage 3: Generate model elements for a single layer/diagram type."""
    prompt_file = PROMPT_MAP.get((mode, layer_key))
    if not prompt_file:
        raise ValueError(f"No prompt template for mode={mode}, layer={layer_key}")
    template = (PROMPTS_DIR / prompt_file).read_text()
    reqs_json = [r.model_dump() for r in requirements]
    prompt = template.format(requirements=reqs_json)
    return call_llm(
        prompt=prompt, cost_tracker=tracker,
        call_type="generate", stage=f"generate_{layer_key}",
        client=client,
    )
```

- [ ] **Step 3: Write Capella prompt templates (4 files)**

Each prompt template should:
- Accept `{requirements}` placeholder (JSON array of requirements)
- Describe the target Arcadia layer and its element types with field definitions
- Include a worked example using the SAR/Keep Station data from the Davie presentation
- Specify the exact JSON output structure expected (matching the Pydantic models)
- Instruct the LLM to use unique IDs with appropriate prefixes (OE-, OC-, OS-, OA-, SF-, LC-, PC-, etc.)

Write: `prompts/generate_capella_oa.txt`, `generate_capella_sa.txt`, `generate_capella_la.txt`, `generate_capella_pa.txt`

- [ ] **Step 4: Write Rhapsody prompt templates (6 files)**

Each prompt template should:
- Accept `{requirements}` placeholder
- Describe the target SysML diagram type and element types per ISO/IEC/IEEE 24641:2023
- Include a worked example
- Specify the exact JSON output structure expected
- Use appropriate ID prefixes (REQD-, BDD-, IBD-, ACT-, LIF-, MSG-, ST-, etc.)

Write: `prompts/generate_rhapsody_req.txt`, `generate_rhapsody_bdd.txt`, `generate_rhapsody_ibd.txt`, `generate_rhapsody_act.txt`, `generate_rhapsody_seq.txt`, `generate_rhapsody_stm.txt`

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_stages.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/stages/generate.py prompts/generate_*.txt tests/test_stages.py
git commit -m "feat: add pipeline stage 3 (layer-by-layer model generation) with 10 prompt templates"
```

---

### Task 8: Pipeline Stages 4-5 (Link & Instruct)

**Files:**
- Create: `src/stages/link.py`
- Create: `src/stages/instruct.py`
- Write: `prompts/link.txt`
- Write: `prompts/instruct_capella.txt`
- Write: `prompts/instruct_rhapsody.txt`
- Update: `tests/test_stages.py`

- [ ] **Step 1: Write link stage tests**

```python
def test_link_stage_returns_links(sample_requirements):
    elements = {
        "operational_analysis": {
            "activities": [{"id": "OA-003", "name": "Maintain Station"}]
        }
    }
    mock_response = {
        "links": [
            {"id": "LNK-001", "source": "OA-003", "target": "REQ-SAR-004", "type": "satisfies", "description": "Station keeping satisfies positioning requirement"}
        ]
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.link.call_llm", return_value=mock_response):
        result = generate_links("capella", elements, sample_requirements, tracker)
    assert len(result["links"]) == 1
    assert result["links"][0]["type"] == "satisfies"
```

- [ ] **Step 2: Write link.py and link.txt prompt**

`link.py` takes the full element set across all layers + requirements, sends them to the LLM, and returns a list of Link objects. The prompt includes the valid link types for the target notation (Arcadia vs SysML).

- [ ] **Step 3: Write instruct stage tests**

```python
def test_instruct_stage_returns_steps():
    model_data = {"layers": {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Test"}]}}}
    mock_response = {
        "tool": "Capella 7.0",
        "steps": [
            {"step": 1, "action": "Create project", "detail": "File > New > Capella Project", "layer": "general"}
        ]
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.instruct.call_llm", return_value=mock_response):
        result = generate_instructions("capella", model_data, tracker)
    assert result["steps"][0]["action"] == "Create project"
```

- [ ] **Step 4: Write instruct.py and prompt templates**

`instruct.py` takes the complete model and generates step-by-step recreation instructions. Two prompt templates: `instruct_capella.txt` (references Capella 7.0 menu paths) and `instruct_rhapsody.txt` (references IBM Rhapsody 10.0 menu paths).

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_stages.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/stages/link.py src/stages/instruct.py prompts/link.txt prompts/instruct_*.txt tests/test_stages.py
git commit -m "feat: add pipeline stages 4-5 (link generation and recreation instructions)"
```

---

### Task 9: Pipeline Orchestrator

**Files:**
- Create: `src/pipeline.py`
- Create: `tests/test_pipeline.py`

The orchestrator ties all 5 stages together and emits SSE events for real-time progress.

- [ ] **Step 1: Write pipeline tests**

```python
# tests/test_pipeline.py
from unittest.mock import patch, MagicMock, AsyncMock
from src.pipeline import run_pipeline, estimate_cost
from src.models import Requirement


def test_estimate_cost():
    reqs = [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")]
    estimate = estimate_cost(
        requirements=reqs,
        mode="capella",
        selected_layers=["operational_analysis", "system_analysis"],
        model="anthropic/claude-sonnet-4",
    )
    assert "total_calls" in estimate
    assert estimate["total_calls"] == 5  # analyze + generate(2) + link + instruct
    assert "estimated_min_cost" in estimate
    assert "estimated_max_cost" in estimate
    assert estimate["estimated_min_cost"] > 0


def test_estimate_cost_skips_clarify():
    """Clarify is conditional, so estimate shows it separately."""
    reqs = [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")]
    estimate = estimate_cost(reqs, "capella", ["operational_analysis"], "anthropic/claude-sonnet-4")
    assert "clarify_note" in estimate
```

- [ ] **Step 2: Write pipeline.py**

```python
# src/pipeline.py
import json
from datetime import datetime, timezone
from typing import Callable

from src.config import MODEL
from src.cost_tracker import CostTracker
from src.llm_client import create_client
from src.models import MBSEModel, Meta, Requirement, Link
from src.stages.analyze import analyze_requirements
from src.stages.clarify import apply_clarifications
from src.stages.generate import generate_layer
from src.stages.link import generate_links
from src.stages.instruct import generate_instructions


def estimate_cost(requirements, mode, selected_layers, model):
    """Pre-run cost estimation. Returns dict with call breakdown and cost range."""
    # Calculate based on: 1 analyze + N generate (one per layer) + 1 link + 1 instruct
    ...


def run_pipeline(
    requirements: list[Requirement],
    mode: str,
    selected_layers: list[str],
    model: str,
    provider: str,
    clarifications: dict[str, str] | None = None,
    emit: Callable[[dict], None] | None = None,
    cost_log_path=None,
) -> MBSEModel:
    """Run the full 5-stage pipeline. Returns an MBSEModel.

    emit: callback for SSE events, called with {"stage": ..., "status": ..., "detail": ...}
    """
    tracker = CostTracker(model=model, cost_log_path=cost_log_path)
    client = create_client()
    _emit = emit or (lambda e: None)

    # Stage 1: Analyze
    _emit({"stage": "analyze", "status": "running", "detail": "Analyzing requirements..."})
    analysis = analyze_requirements(requirements, tracker, client=client)
    _emit({"stage": "analyze", "status": "complete", "detail": f"{len(analysis.get('flagged', []))} issues found"})

    # Stage 2: Clarify (conditional)
    if clarifications:
        _emit({"stage": "clarify", "status": "running", "detail": "Applying clarifications..."})
        requirements = apply_clarifications(requirements, clarifications)
        _emit({"stage": "clarify", "status": "complete"})

    # Stage 3: Generate (layer by layer)
    layers = {}
    for layer_key in selected_layers:
        _emit({"stage": "generate", "status": "running", "detail": f"Generating {layer_key}..."})
        layers[layer_key] = generate_layer(mode, layer_key, requirements, tracker, client=client)
        _emit({"stage": "generate", "status": "complete", "detail": f"{layer_key} complete"})

    # Stage 4: Link
    _emit({"stage": "link", "status": "running", "detail": "Generating cross-element links..."})
    link_result = generate_links(mode, layers, requirements, tracker, client=client)
    links = [Link(**l) for l in link_result.get("links", [])]
    _emit({"stage": "link", "status": "complete", "detail": f"{len(links)} links created"})

    # Stage 5: Instruct
    _emit({"stage": "instruct", "status": "running", "detail": "Generating recreation instructions..."})
    instructions = generate_instructions(mode, {"layers": layers}, tracker, client=client)
    _emit({"stage": "instruct", "status": "complete"})

    # Build final model
    model_obj = MBSEModel(
        meta=Meta(
            source_file="uploaded", mode=mode, selected_layers=selected_layers,
            llm_provider=provider, llm_model=model,
            cost=tracker.get_summary(),
        ),
        requirements=requirements,
        layers=layers,
        links=links,
        instructions=instructions,
    )

    # Log cost
    tracker.flush_log(run_type="pipeline_run", source_file=model_obj.meta.source_file,
                      mode=mode, layers=selected_layers)

    _emit({"stage": "done", "status": "complete", "detail": tracker.format_cost_line()})
    return model_obj
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_pipeline.py -v`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add pipeline orchestrator with cost estimation and SSE events"
```

---

### Task 10: Agent Tools & Chat

**Files:**
- Create: `src/agent/tools.py`
- Create: `src/agent/chat.py`
- Write: `prompts/agent_system.txt`
- Create: `tests/test_agent_tools.py`

- [ ] **Step 1: Write agent tools tests**

```python
# tests/test_agent_tools.py
import json
from src.agent.tools import apply_tool, TOOL_DEFINITIONS
from src.models import MBSEModel, Meta, Requirement, Link


def make_test_model():
    return MBSEModel(
        meta=Meta(source_file="test.xlsx", mode="capella", selected_layers=["operational_analysis"],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[Requirement(id="REQ-001", text="Test", source_dig="DIG-001")],
        layers={"operational_analysis": {"entities": [{"id": "OE-001", "name": "Test Entity", "type": "OperationalEntity", "actors": []}]}},
        links=[Link(id="LNK-001", source="OE-001", target="REQ-001", type="satisfies", description="test")],
        instructions={"tool": "Capella 7.0", "steps": []},
    )


def test_add_element():
    model = make_test_model()
    result = apply_tool(model, "add_element", {
        "layer": "operational_analysis",
        "collection": "entities",
        "element": {"id": "OE-002", "name": "New Entity", "type": "OperationalEntity", "actors": []}
    })
    assert result["success"]
    entities = model.layers["operational_analysis"]["entities"]
    assert len(entities) == 2
    assert entities[1]["id"] == "OE-002"


def test_modify_element():
    model = make_test_model()
    result = apply_tool(model, "modify_element", {"element_id": "OE-001", "updates": {"name": "Renamed Entity"}})
    assert result["success"]
    assert model.layers["operational_analysis"]["entities"][0]["name"] == "Renamed Entity"


def test_remove_element_cascades_links():
    model = make_test_model()
    result = apply_tool(model, "remove_element", {"element_id": "OE-001", "cascade": True})
    assert result["success"]
    assert len(model.layers["operational_analysis"]["entities"]) == 0
    assert len(model.links) == 0  # Link was cascaded


def test_add_link():
    model = make_test_model()
    result = apply_tool(model, "add_link", {
        "link": {"id": "LNK-002", "source": "OE-001", "target": "REQ-001", "type": "involves", "description": "new link"}
    })
    assert result["success"]
    assert len(model.links) == 2


def test_tool_definitions_are_valid_openai_format():
    for tool in TOOL_DEFINITIONS:
        assert "type" in tool and tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "parameters" in tool["function"]
```

- [ ] **Step 2: Write tools.py**

Define `TOOL_DEFINITIONS` as a list of OpenAI-format tool schemas. Implement `apply_tool(model, tool_name, arguments) -> dict` that modifies the MBSEModel in-place and returns `{"success": True/False, "message": "..."}`.

Tools to implement: `add_element`, `modify_element`, `remove_element`, `add_link`, `modify_link`, `remove_link`, `regenerate_layer`, `add_instruction_step`, `list_elements`, `list_links`, `get_element_details`.

- [ ] **Step 3: Write chat.py**

```python
# src/agent/chat.py
from src.agent.tools import TOOL_DEFINITIONS, apply_tool
from src.cost_tracker import CostTracker
from src.llm_client import call_llm_with_tools
from src.models import MBSEModel


def chat_with_agent(
    model: MBSEModel,
    user_message: str,
    conversation_history: list[dict],
    tracker: CostTracker,
) -> tuple[str, list[dict]]:
    """Send a message to the chat agent. Returns (agent_response_text, updated_history).

    The agent may call tools to modify the model. Tool calls are executed automatically.
    """
    ...
```

The chat function:
1. Loads `prompts/agent_system.txt` as the system prompt
2. Appends the user message to conversation history
3. Calls `call_llm_with_tools()` with TOOL_DEFINITIONS
4. If the response contains tool calls, executes them via `apply_tool()` and loops
5. Returns the final text response and updated history

- [ ] **Step 4: Write agent_system.txt**

The system prompt should describe the agent's role (modifying MBSE models), list available tools with examples, and instruct it to explain what changes it made after each operation.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_agent_tools.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent/tools.py src/agent/chat.py prompts/agent_system.txt tests/test_agent_tools.py
git commit -m "feat: add chat agent with 11 tools for model modification"
```

---

### Task 11: Export Functionality

**Files:**
- Create: `src/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Write export tests**

```python
# tests/test_exporter.py
import json
from pathlib import Path
from src.exporter import export_json, export_xlsx, export_text
from tests.test_agent_tools import make_test_model


def test_export_json(tmp_path):
    model = make_test_model()
    path = export_json(model, tmp_path / "output.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["meta"]["mode"] == "capella"


def test_export_xlsx(tmp_path):
    model = make_test_model()
    path = export_xlsx(model, tmp_path / "output.xlsx")
    assert path.exists()
    import openpyxl
    wb = openpyxl.load_workbook(path)
    assert "Links" in wb.sheetnames


def test_export_text(tmp_path):
    model = make_test_model()
    path = export_text(model, tmp_path / "output.txt")
    assert path.exists()
    content = path.read_text()
    assert "Capella" in content or "capella" in content
```

- [ ] **Step 2: Write exporter.py**

Three export functions:
- `export_json(model, path)`: serialize MBSEModel to formatted JSON file
- `export_xlsx(model, path)`: create workbook with one sheet per layer, a Links sheet, and an Instructions sheet using openpyxl
- `export_text(model, path)`: formatted plain text hierarchical list with indentation showing the model structure, followed by link descriptions and instructions

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_exporter.py -v`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add src/exporter.py tests/test_exporter.py
git commit -m "feat: add JSON, XLSX, and text export functionality"
```

---

### Task 12: FastAPI Backend

**Files:**
- Create: `src/web/app.py`

**Reference:** Follow patterns from `/Users/jude/Documents/projects/Requirements/src/web/app.py` for endpoint structure, Job dataclass, SSE streaming, git-based update mechanism, and settings management.

- [ ] **Step 1: Write app.py with all endpoints**

Endpoints to implement:

```
GET  /                     → HTML page (Jinja2 template)
POST /upload               → Accept XLSX/CSV file, parse, return requirement count
POST /estimate             → Dry-run cost estimation (pre-run warning)
POST /run                  → Start pipeline run (returns job_id)
GET  /stream/{job_id}      → SSE event stream for pipeline progress
GET  /job/{job_id}         → Get job result (MBSEModel JSON)
POST /job/{job_id}/edit    → Inline edit: modify model in-place
POST /job/{job_id}/chat    → Chat agent message
GET  /job/{job_id}/export/{format}  → Export as json/xlsx/text
POST /cancel/{job_id}      → Cancel running job
GET  /settings             → Get current settings
POST /settings             → Update settings (.env file)
GET  /models               → List model catalogue
GET  /check-updates        → Git-based update check
POST /update               → Git pull + pip install
GET  /cost-history          → Read cost_log.jsonl, return summary
```

Key implementation details:
- Use `Job` dataclass with `id`, `status`, `events`, `model` (MBSEModel | None), `task` (asyncio.Task | None), `cancelled`, `conversation_history`
- Run pipeline in `asyncio.create_task()` with an emit callback that appends to `job.events`
- SSE endpoint: `StreamingResponse` that yields events from `job.events` as `data: {json}\n\n`
- `/upload`: save file to temp path, call `parse_requirements_file()`, store parsed requirements on the job
- `/estimate`: call `pipeline.estimate_cost()` with current settings
- `/run`: create Job, start pipeline task, return job_id
- `/job/{id}/edit`: receive `{element_id, updates}` or `{action: "add"|"remove", ...}`, apply to `job.model` using agent tools
- `/job/{id}/chat`: receive `{message}`, call `chat_with_agent()`, return response
- Settings endpoints: read/write `.env` file in PACKAGE_ROOT, reload config
- Update endpoints: identical to reqdecomp (subprocess `git fetch`, `git pull`, `pip install -e .`)
- Cost history: read `output/cost_log.jsonl`, compute aggregates

- [ ] **Step 2: Commit**

```bash
git add src/web/app.py
git commit -m "feat: add FastAPI backend with all endpoints"
```

---

### Task 13: CLI Entry Point

**Files:**
- Create: `src/main.py`

**Reference:** Follow `/Users/jude/Documents/projects/Requirements/src/main.py` for argparse and server start pattern.

- [ ] **Step 1: Write main.py**

```python
# src/main.py
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="MBSE Model Generator")
    parser.add_argument("--web", action="store_true", help="Start web interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--setup", action="store_true", help="Interactive setup wizard")
    args = parser.parse_args()

    if args.setup:
        _run_setup()
    elif args.web:
        _start_web(args.host, args.port)
    else:
        parser.print_help()


def _start_web(host: str, port: int):
    import uvicorn
    from src.web.app import app
    print(f"\n  MBSE Model Generator")
    print(f"  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _run_setup():
    """Interactive setup: prompt for API keys and write .env file."""
    from pathlib import Path
    from src.config import PACKAGE_ROOT
    env_path = PACKAGE_ROOT / ".env"
    print("\n  MBSE Generator Setup\n")
    provider = input("  Provider (anthropic/openrouter/local) [openrouter]: ").strip() or "openrouter"
    lines = [f"PROVIDER={provider}"]
    if provider in ("anthropic", "openrouter"):
        key_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENROUTER_API_KEY"
        key = input(f"  {key_name}: ").strip()
        lines.append(f"{key_name}={key}")
    if provider == "local":
        url = input("  LOCAL_LLM_URL [http://localhost:11434/v1]: ").strip() or "http://localhost:11434/v1"
        lines.append(f"LOCAL_LLM_URL={url}")
    model = input("  MODEL [anthropic/claude-sonnet-4]: ").strip() or "anthropic/claude-sonnet-4"
    lines.append(f"MODEL={model}")
    mode = input("  DEFAULT_MODE (capella/rhapsody) [capella]: ").strip() or "capella"
    lines.append(f"DEFAULT_MODE={mode}")
    env_path.write_text("\n".join(lines) + "\n")
    print(f"\n  Config saved to {env_path}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI works**

Run: `mbsegen --help`
Expected: Shows help text with `--web`, `--setup` options.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: add CLI entry point with web server and setup wizard"
```

---

### Task 14: Frontend HTML Template

**Files:**
- Create: `src/web/templates/index.html`

**Reference:** Follow `/Users/jude/Documents/projects/Requirements/src/web/templates/index.html` for Jinja2 pattern.

- [ ] **Step 1: Write index.html**

Jinja2 template with the two-panel layout from the spec wireframe:

**Left panel (320px):**
- Mode toggle (Capella/Rhapsody segmented control)
- Layer checkboxes (dynamically populated based on mode, using `{{ capella_layers | tojson }}` and `{{ rhapsody_diagrams | tojson }}` from server)
- File upload drop zone (drag-and-drop + click-to-browse)
- LLM provider three-way selector (Anthropic/OpenRouter/Local)
- Generate button

**Right panel:**
- Tab bar: Model Tree | Links | Instructions | Raw JSON + Export dropdown
- Model tree container (populated by JS)
- Chat agent panel at bottom (collapsed by default)

**Top bar:**
- "MBSE Generator" title + version
- Settings button (opens modal)
- Update button

**Settings modal:**
- API key inputs (Anthropic, OpenRouter, Local URL)
- Model selector dropdown (populated from `{{ model_catalogue | tojson }}`)
- Each model shows name, price, quality, description, pros/cons
- Cost History section

**Cost confirmation modal:**
- Estimated calls breakdown
- Cost range
- Model name
- Proceed / Cancel buttons

**Clarification modal:**
- Shows flagged requirements with questions
- Text inputs for each clarification
- Continue button

Template receives from server: `version`, `model_catalogue`, `capella_layers`, `rhapsody_diagrams`, `current_settings`

- [ ] **Step 2: Commit**

```bash
git add src/web/templates/index.html
git commit -m "feat: add HTML template with two-panel layout"
```

---

### Task 15: Frontend CSS

**Files:**
- Create: `src/web/static/style.css`

**Reference:** Follow `/Users/jude/Documents/projects/Requirements/src/web/static/style.css` for the dark theme color scheme and component patterns.

- [ ] **Step 1: Write style.css**

Dark theme matching reqdecomp:
- Background: `#0a0a12`, panels: `#0d0d1a`, borders: `#2a2a4a`
- Accent: `#7c7cff` (interactive elements, active tabs, toggle active state)
- Green: `#1a5a1a` background / `#4ade80` text (generate button, success states)
- Text: `#e2e8f0` primary, `#888` secondary, `#555` muted

Key CSS components:
- `.top-bar` -- fixed top, flex row, app title + buttons
- `.main-content` -- flex row, full height minus top bar
- `.left-panel` -- 320px fixed width, overflow-y auto, section dividers
- `.right-panel` -- flex 1, column layout
- `.mode-toggle` -- segmented control with active/inactive states
- `.layer-checkbox` -- custom checkbox styling
- `.upload-zone` -- dashed border, drag-over state, file-loaded state
- `.provider-selector` -- three-way segmented control
- `.generate-btn` -- green, full width, hover effect
- `.tab-bar` -- horizontal tabs with active indicator
- `.tree-node` -- collapsible with expand/collapse arrow, edit icon hover
- `.element-row` -- flex row, ID badge, name, type badge, action icons
- `.chat-panel` -- bottom of right panel, collapsible
- `.modal` -- centered overlay with backdrop blur
- `.toast` -- bottom-right notification, fade-in/out animation
- `.progress-bar` -- dark track, colored fill, smooth transition

- [ ] **Step 2: Commit**

```bash
git add src/web/static/style.css
git commit -m "feat: add dark theme CSS matching reqdecomp style"
```

---

### Task 16: Frontend JavaScript

**Files:**
- Create: `src/web/static/app.js`

**Reference:** Follow `/Users/jude/Documents/projects/Requirements/src/web/static/app.js` for SSE handling, update checking, and settings persistence patterns.

This is the largest frontend file. Organize into clear sections.

- [ ] **Step 1: Write app.js -- State Management section**

```javascript
// Global state
let currentModel = null;       // MBSEModel JSON from server
let currentJobId = null;       // Active job ID
let selectedMode = 'capella';  // 'capella' or 'rhapsody'
let selectedLayers = [];       // Selected layer/diagram keys
let uploadedFile = null;       // File object from upload
let conversationHistory = [];  // Chat agent message history
```

- [ ] **Step 2: Write app.js -- Mode Toggle & Layer Selection**

Handle mode toggle clicks: switch between Capella layers and Rhapsody diagram checkboxes. Store selections in `selectedLayers`.

- [ ] **Step 3: Write app.js -- File Upload**

Drag-and-drop handler + click-to-browse. On file selected: POST to `/upload` as FormData, show requirement count confirmation.

- [ ] **Step 4: Write app.js -- Pipeline Execution (Generate button)**

On Generate click:
1. POST to `/estimate` with current settings → show cost confirmation modal
2. On confirm: POST to `/run` with settings → receive `job_id`
3. Connect to `/stream/{job_id}` via EventSource (SSE)
4. Render progress per stage (progress bars, status messages, running cost)
5. On completion: GET `/job/{job_id}` → store as `currentModel`, render tree

- [ ] **Step 5: Write app.js -- Tree Rendering**

Recursive tree renderer:
- Groups elements by layer > diagram type
- Each layer section is collapsible with "Regen" button
- Each element row shows: ID (muted code), name (editable on click), type badge
- Edit icon → opens inline edit form
- Delete icon → confirm dialog → POST to `/job/{id}/edit` with remove action
- "+ Add" button at bottom of each group

- [ ] **Step 6: Write app.js -- Output Tabs**

Tab switching logic for: Model Tree, Links, Instructions, Raw JSON.
- Links tab: render table from `currentModel.links`
- Instructions tab: render ordered step list from `currentModel.instructions.steps`
- Raw JSON tab: syntax-highlighted `JSON.stringify(currentModel, null, 2)`

- [ ] **Step 7: Write app.js -- Inline Editing**

Click edit icon → element row becomes editable (input fields). On save: POST to `/job/{id}/edit`. On success: update `currentModel`, re-render affected tree section.

- [ ] **Step 8: Write app.js -- Chat Agent**

Chat panel expand/collapse. Message input + send button. On send: POST to `/job/{id}/chat` with message and history. Render agent response. Update `currentModel` if agent made changes. Re-render tree.

- [ ] **Step 9: Write app.js -- Export**

Export dropdown. On click: open `/job/{id}/export/{format}` as download link.

- [ ] **Step 10: Write app.js -- Settings Modal**

Open/close modal. Populate with current settings. Save: POST to `/settings`. Model selector with catalogue info.

- [ ] **Step 11: Write app.js -- Git-Based Updates**

On page load: `checkUpdatesQuietly()` → GET `/check-updates`. If updates available: show pulsing banner with commit list. "Update Now" button: POST `/update`. Show restart notice on success.

Follow the reqdecomp pattern exactly (see reqdecomp `app.js` lines 750-924).

- [ ] **Step 12: Write app.js -- Cost History**

In Settings modal: GET `/cost-history`, render summary (total spend, per-day, per-run averages).

- [ ] **Step 13: Write app.js -- Clarification Flow**

If pipeline analyze stage returns flagged requirements: show clarification modal with questions. On submit: re-run pipeline with clarifications dict.

- [ ] **Step 14: Write app.js -- Toast Notifications**

`showToast(message, type)` function for success/error/info notifications. Auto-dismiss after 4 seconds.

- [ ] **Step 15: Commit**

```bash
git add src/web/static/app.js
git commit -m "feat: add frontend JavaScript with tree view, chat agent, and all interactivity"
```

---

### Task 17: Integration & Push to GitHub

**Files:**
- Update: `src/stages/__init__.py` (re-export stage functions)
- Verify: All tests pass
- Push to GitHub

- [ ] **Step 1: Update stages/__init__.py with exports**

```python
from src.stages.analyze import analyze_requirements
from src.stages.clarify import apply_clarifications
from src.stages.generate import generate_layer
from src.stages.link import generate_links
from src.stages.instruct import generate_instructions
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Verify the web server starts**

Run: `mbsegen --web`
Expected: Server starts on http://127.0.0.1:8000, page loads with the two-panel layout, mode toggle works, settings modal opens.

- [ ] **Step 4: Manual smoke test**

1. Open http://127.0.0.1:8000
2. Toggle between Capella and Rhapsody modes → layer checkboxes change
3. Upload a sample XLSX file → requirement count shown
4. Open Settings → model catalogue displayed
5. Check Updates → shows current status

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "feat: integration fixes and final wiring"
```

- [ ] **Step 6: Push to GitHub**

```bash
git push -u origin main
```

Expected: Code appears at https://github.com/jude-sph/MBSE

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Project scaffolding | pyproject.toml, dirs, .env.example |
| 2 | Config & model catalogue | src/config.py |
| 3 | Pydantic data models | src/models/{core,capella,rhapsody}.py |
| 4 | Cost tracker & LLM client | src/cost_tracker.py, src/llm_client.py |
| 5 | File parser | src/parser.py |
| 6 | Pipeline stages 1-2 | src/stages/{analyze,clarify}.py + prompts |
| 7 | Pipeline stage 3 | src/stages/generate.py + 10 prompts |
| 8 | Pipeline stages 4-5 | src/stages/{link,instruct}.py + prompts |
| 9 | Pipeline orchestrator | src/pipeline.py |
| 10 | Agent tools & chat | src/agent/{tools,chat}.py + agent prompt |
| 11 | Export functionality | src/exporter.py |
| 12 | FastAPI backend | src/web/app.py |
| 13 | CLI entry point | src/main.py |
| 14 | HTML template | src/web/templates/index.html |
| 15 | CSS styling | src/web/static/style.css |
| 16 | Frontend JavaScript | src/web/static/app.js |
| 17 | Integration & push | Tests, smoke test, git push |
