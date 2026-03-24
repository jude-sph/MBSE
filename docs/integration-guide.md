# Reqdecomp + MBSE Integration Guide

> **For another Claude Code instance:** This document provides complete context for integrating the Requirements Decomposition (reqdecomp) and MBSE Model Generator apps into a unified workflow. Written by the Claude instance that built the MBSE app.

## 1. Project Locations

- **Reqdecomp:** `/Users/jude/Documents/projects/Requirements`
- **MBSE:** `/Users/jude/Documents/projects/MBSE`
- **GitHub:** https://github.com/jude-sph/MBSE.git (MBSE only; reqdecomp at separate repo)

## 2. The Engineer's Workflow (What We're Integrating)

The real workflow is sequential:

```
Raw high-level requirements (DIG text from GTR-SDS.xlsx)
    ↓ reqdecomp
Decomposed requirements (node_id, technical_requirement, dig_id, ...)
    ↓ MBSE app
MBSE model structure (entities, capabilities, functions, links, ...)
    ↓ Engineer
Recreated in Capella or Rhapsody modeling tool
```

Currently the engineer must:
1. Run reqdecomp, export results.xlsx
2. Download the file
3. Open MBSE app, upload the same file
4. Generate model

The goal is to eliminate steps 2-3 -- the engineer should be able to decompose in reqdecomp and flow directly into MBSE modeling without file juggling.

## 3. Reqdecomp Architecture (Summary)

### Tech Stack
- Python 3.11+, FastAPI, Uvicorn, Pydantic 2.0+
- openpyxl, anthropic/openai SDKs, tqdm
- Vanilla JS frontend, dark theme, SSE for progress
- Package: `pip install -e .`, CLI: `reqdecomp --web`

### Core Data Model

```python
# src/models.py
RequirementNode:
    level: int                      # 1-4 (Whole Ship → Equipment)
    level_name: str                 # "Whole Ship", "Major System", "Subsystem", "Equipment"
    allocation: str                 # "GTR", "SDS", "GTR / SDS"
    chapter_code: str               # Reference chapter
    derived_name: str               # Short title
    technical_requirement: str      # "The [System] shall..." (IEEE 29481)
    rationale: str
    system_hierarchy_id: str        # System Breakdown Structure ID
    acceptance_criteria: Optional[str]
    verification_method: list[str]  # ["Test", "Inspection", "Analysis"]
    verification_event: list[str]   # ["FAT", "HAT", "SAT", "Sea Trials"]
    test_case_descriptions: list[str]
    confidence_notes: Optional[str]
    decomposition_complete: bool
    children: list[RequirementNode] # Recursive tree

RequirementTree:
    dig_id: str                     # Design Instruction & Guideline ID (e.g., "9584")
    dig_text: str                   # Original high-level requirement text
    root: Optional[RequirementNode]
    validation: Optional[ValidationResult]
    cost: Optional[CostSummary]
```

### Decomposition Pipeline (per DIG)

1. **Decompose** -- Recursive LLM calls building a tree (depth 1-4, breadth up to 3)
2. **V&V** -- Generate verification & validation data for each node
3. **Structural Validation** -- Python rule checks (shall format, array lengths, etc.)
4. **Semantic Judge** -- LLM reviews entire tree for coherence
5. **Refine** -- LLM fixes issues found by judge
6. **Export** -- Flatten tree to XLSX rows

### Output Format (results.xlsx)

```
Columns: dig_id, dig_text, node_id, parent_id, level, level_name,
         allocation, chapter_code, derived_name, technical_requirement,
         rationale, system_hierarchy_id, confidence_notes,
         acceptance_criteria, verification_method, verification_event,
         test_case_descriptions
```

Each row is one decomposed requirement. `node_id` format: `"{dig_id}-{counter}"` (e.g., "9584-1", "9584-2").

### Key Reqdecomp Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/run` | Start decomposition job |
| GET | `/stream/{job_id}` | SSE progress events |
| GET | `/results` | List completed results |
| GET | `/results/{dig_id}` | Full tree JSON for one DIG |
| GET | `/export` | Download results.xlsx |

### Reqdecomp SSE Events

```json
{"type": "dig_started", "dig_id": "9584", "index": 1, "total": 3}
{"type": "phase", "dig_id": "9584", "phase": "decompose", "detail": "Building tree"}
{"type": "dig_complete", "dig_id": "9584", "nodes": 42, "cost": 0.48}
{"type": "complete", "total_digs": 3, "total_nodes": 127, "total_cost": 1.25}
```

### Output JSON Structure (per DIG)

Each completed DIG is saved to `output/json/{dig_id}.json` as a serialized `RequirementTree`.

## 4. MBSE App Architecture (Summary)

### Tech Stack
- Python 3.11+, FastAPI, Uvicorn, Pydantic 2.0+
- openpyxl, httpx, anthropic/openai SDKs
- Vanilla JS frontend, dark theme, SSE for progress
- Package: `pip install -e .`, CLI: `mbsegen --web`

### Core Data Model

```python
# src/models/core.py
Requirement(id, text, source_dig)
Link(id, source, target, type, description)
Meta(source_file, mode, selected_layers, llm_provider, llm_model, cost, generated_at)
MBSEModel(meta, requirements, layers, links, instructions)
ProjectModel extends MBSEModel:
    project: ProjectMeta(name, created_at, last_modified)
    batches: list[BatchRecord]
    chat_history: list[dict]
```

### MBSE Pipeline (5 stages)

1. **Analyze** -- Flag ambiguous requirements
2. **Clarify** -- Apply user clarifications (conditional)
3. **Generate** -- Layer-by-layer model element generation (1 LLM call per layer)
4. **Link** -- Cross-element traceability relationships
5. **Instruct** -- Step-by-step Capella/Rhapsody recreation instructions

### What MBSE Expects as Input

The MBSE parser (`src/parser.py`) accepts XLSX/CSV with flexible column detection:

```python
_ID_ALIASES = ["id", "node_id", "req_id", "requirement_id", "dng"]
_TEXT_ALIASES = ["text", "technical_requirement", "requirement_text", ...]
_SOURCE_ALIASES = ["source_dig", "dig_id", "dig", "dng", "source"]
```

It already handles reqdecomp output format natively:
- `node_id` → requirement ID
- `technical_requirement` → requirement text
- `dig_id` → source DIG reference

### Project Workspace

The MBSE app uses persistent projects (`project.json`) with batch processing. Engineers upload requirements in batches of 1-10, each batch extends the existing model. The LLM sees the existing model context when generating new elements.

### Key MBSE Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/upload` | Parse requirements file |
| POST | `/run` | Start MBSE pipeline |
| GET | `/stream/{job_id}` | SSE progress |
| GET | `/project` | Get current project |
| POST | `/project/new` | Create new project |
| POST | `/project/chat` | Chat with agent |

## 5. Shared Infrastructure

Both apps share ~70% of their infrastructure code (written by the same developer with the same patterns):

| Component | Reqdecomp | MBSE | Identical? |
|-----------|-----------|------|-----------|
| LLM Client | `src/llm_client.py` | `src/llm_client.py` | ~95% (MBSE adds local provider + tool calling) |
| Cost Tracker | `src/cost_tracker.py` | `src/cost_tracker.py` | ~90% (MBSE adds JSONL logging) |
| Config | `src/config.py` | `src/config.py` | ~80% (same MODEL_PRICING, MODEL_CATALOGUE) |
| Web Server | FastAPI + SSE | FastAPI + SSE | Same patterns, different endpoints |
| Frontend | Vanilla JS, dark theme | Vanilla JS, dark theme | Same styling, different UI |
| Update Mechanism | Git pull + pip install | Git pull + pip install | Identical |
| Package Structure | `pip install -e .` | `pip install -e .` | Same |

### .env Configuration (shared format)

Both use the same .env structure:
```
PROVIDER=openrouter
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
MODEL=anthropic/claude-sonnet-4
```

## 6. Integration Approaches

### Option A: API Bridge (Recommended First Step)

Add a "Send to MBSE" button in reqdecomp's results page that POSTs decomposed requirements directly to the MBSE app's `/upload` endpoint (or a new dedicated endpoint).

**Reqdecomp side changes:**
- Add a button on the results page for each DIG: "Send to MBSE →"
- When clicked: fetch the tree JSON from `/results/{dig_id}`, flatten to the format MBSE expects, POST to MBSE's API

**MBSE side changes:**
- Add `POST /api/import-from-reqdecomp` endpoint that accepts reqdecomp's tree JSON directly
- Convert `RequirementTree` → `list[Requirement]` (flatten tree, use `node_id` as ID, `technical_requirement` as text, `dig_id` as source_dig)
- Populate `parsed_requirements` and return count

**Pros:** Minimal changes to either codebase, both apps stay independent
**Cons:** Two servers must be running, engineer still switches between browser tabs

### Option B: Combined Single App

Merge both into one app with a two-phase workflow:

```
Phase 1: Decompose (reqdecomp logic)
  ↓ (stays in memory, no file export needed)
Phase 2: Model (MBSE logic)
```

**Architecture:**
- One FastAPI server, one frontend
- Decomposition becomes "Stage 0" before the existing MBSE pipeline
- The UI has two modes: "Decompose" and "Model"
- Decomposed requirements flow directly into the MBSE pipeline

**Shared code to extract:**
- LLM client → single module
- Cost tracker → single module
- Config + model catalogue → single module
- Update mechanism → single module

**Pros:** Seamless workflow, single install, no file juggling
**Cons:** Larger codebase, more complex, reqdecomp is already stable

### Option C: Shared Library + Unified Launcher

Extract common code into a shared package, keep apps separate but installable together:

```
pip install shiptools  # installs both
shiptools decompose --web  # or
shiptools model --web      # or
shiptools --web            # unified launcher with both
```

## 7. Data Format Compatibility

### Reqdecomp Output → MBSE Input (Already Compatible)

The MBSE parser already handles reqdecomp output columns natively. The mapping:

| Reqdecomp Column | MBSE Requirement Field | Notes |
|-----------------|----------------------|-------|
| `node_id` | `id` | e.g., "9584-1" |
| `technical_requirement` | `text` | "The vessel shall..." |
| `dig_id` | `source_dig` | e.g., "9584" |

Additional reqdecomp columns available but not currently used by MBSE:
- `level`, `level_name` -- could inform which MBSE layers to generate
- `allocation` -- could guide Capella vs operational focus
- `system_hierarchy_id` -- could map to MBSE component hierarchy
- `verification_method`, `verification_event` -- could feed into MBSE link types
- `rationale` -- could enrich LLM context for model generation

### Direct JSON Transfer (For API Bridge)

Reqdecomp's `/results/{dig_id}` returns a full `RequirementTree` JSON. To convert to MBSE's `Requirement` format:

```python
def reqdecomp_tree_to_mbse_requirements(tree_json: dict) -> list[dict]:
    """Convert reqdecomp tree JSON to MBSE requirement list."""
    requirements = []
    dig_id = tree_json["dig_id"]

    def flatten(node, counter=[0]):
        counter[0] += 1
        node_id = f"{dig_id}-{counter[0]}"
        requirements.append({
            "id": node_id,
            "text": node["technical_requirement"],
            "source_dig": dig_id,
        })
        for child in node.get("children", []):
            flatten(child, counter)

    if tree_json.get("root"):
        flatten(tree_json["root"])
    return requirements
```

## 8. Key Technical Considerations

### Concurrent Server Ports

If running both apps simultaneously:
- Reqdecomp: typically port 8000
- MBSE: typically port 8111

For the API bridge approach, MBSE needs to know reqdecomp's URL (could be a config value).

### Shared .env

Both apps read from `.env` in their working directory. If combined, a single `.env` serves both. The env var names are identical (`PROVIDER`, `MODEL`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`).

### Session/State Management

- **Reqdecomp:** Stores results as JSON files in `output/json/`. No project persistence. Each DIG is independent.
- **MBSE:** Persistent `project.json` with batch history. Model accumulates across sessions.

For integration, the flow would be:
1. Reqdecomp decomposes a DIG → result stored in `output/json/{dig_id}.json`
2. MBSE imports selected requirements from that result → adds to project as a batch
3. Project.json records the batch with source: "reqdecomp:{dig_id}"

### Frontend Integration Points

Both frontends share the same dark theme (`#0a0a12` background, `#7c7cff` accent, `#4ade80` green). The CSS is nearly identical. A combined app could reuse 90% of the styling.

Both use SSE for real-time progress with the same pattern:
```javascript
var source = new EventSource('/stream/' + jobId);
source.onmessage = function(e) {
    var event = JSON.parse(e.data);
    // handle event
};
```

### What the Engineer Said About the Workflow

Direct quotes:
- "I'm envisioning a workflow of uploading 1-5 requirements at a time"
- "It's an app dedicated to small batch size tasks"
- "I would create a source input file with perhaps 1-10 requirements focusing on a particular vessel capability"
- "I'd take this list of decomposed mission specific requirements and create an MBSE requirements source file"
- "Total output using reqdecomp and mbse app would be a list of decomposed requirements and mbse structure"

## 9. MBSE-Specific Context (Not Obvious from Code)

### The Arcadia Process

The MBSE app's Capella option follows the Arcadia methodology (5 stages):
1. **Operational Analysis (OA)** -- Who are the actors, what do they do, how do they interact
2. **System Needs Analysis (SA)** -- What must the system do, what are its boundaries
3. **Logical Architecture (LA)** -- What subsystems compose the solution
4. **Physical Architecture (PA)** -- What hardware/software implements the logic
5. **EPBS** -- End-product breakdown for configuration management

Each stage produces 2-12 element collections. The LLM generates all collections for a stage in one call.

### Incremental Model Building

The MBSE app's project workspace was specifically designed for the batch workflow the engineer described. Key features:
- **Context-aware generation:** Each batch sees the existing model, reuses entities
- **ID collision handling:** Auto-renames duplicate IDs
- **Batch history:** Tracks which requirements were processed when
- **Coverage indicator:** Shows which requirements have traceability links

### The "Not Designing a Ship" Principle

The engineer's key insight: "We are NOT designing a ship. We are defining how it achieves its missions." The Operational Analysis stage models the operational reality (missions, actors, interactions) BEFORE touching the vessel's physical design. This is critical for prompt quality -- the LLM must understand it's modeling mission capability, not hardware.

### Chat Agent

The MBSE app has a chat agent that can modify the model via function-calling tools. It sees the full model state (all elements, links, coverage gaps) and can add/modify/remove elements, regenerate layers, and analyze coverage. This agent could potentially also trigger reqdecomp operations in a combined app.

## 10. Recommended Integration Path

1. **Phase 1 (Quick Win):** API bridge. Add "Send to MBSE" button in reqdecomp. Minimal changes, both apps stay independent. Engineers get the seamless flow immediately.

2. **Phase 2 (Unified App):** Combine into one codebase. Reqdecomp becomes the decomposition phase, MBSE becomes the modeling phase. Shared LLM client, config, cost tracking. Single install, single server.

3. **Phase 3 (Web Hosting):** Deploy combined app on Jude's VPS (Flask website at `/Users/jude/Documents/hawraniweb-f/hawraniweb-flask`). Add authentication, run as a separate service behind a reverse proxy.

## 11. File References

### Reqdecomp Key Files
```
src/main.py              -- CLI entry point
src/config.py            -- Config, pricing, model catalogue
src/models.py            -- RequirementNode, RequirementTree, ValidationResult
src/llm_client.py        -- Unified LLM client
src/cost_tracker.py      -- Cost tracking
src/decomposer.py        -- Recursive decomposition pipeline
src/validator.py         -- Structural + semantic validation
src/verifier.py          -- V&V generation
src/refiner.py           -- Judge-driven refinement
src/loader.py            -- XLSX data loading (WorkbookData)
src/exporter.py          -- Tree → XLSX flattening
src/prompts.py           -- Prompt template loading + formatting
src/web/app.py           -- FastAPI server
src/web/static/app.js    -- Frontend JS
src/web/static/style.css -- Dark theme CSS
prompts/                 -- 5 prompt templates
```

### MBSE Key Files
```
src/main.py              -- CLI entry point
src/config.py            -- Config, pricing, model catalogue
src/models/core.py       -- Requirement, MBSEModel, ProjectModel
src/models/capella.py    -- ~45 Arcadia element models
src/models/rhapsody.py   -- ~15 SysML element models
src/llm_client.py        -- Unified LLM client (+ local + tool calling)
src/cost_tracker.py      -- Cost tracking + JSONL logging
src/parser.py            -- XLSX/CSV parsing with column aliases
src/pipeline.py          -- 5-stage pipeline + merge + ID collision fix
src/project.py           -- Project persistence (load/save/backup)
src/exporter.py          -- JSON/XLSX/Text export
src/stages/analyze.py    -- Stage 1: requirement analysis
src/stages/clarify.py    -- Stage 2: clarification
src/stages/generate.py   -- Stage 3: layer-by-layer generation
src/stages/link.py       -- Stage 4: traceability links
src/stages/instruct.py   -- Stage 5: recreation instructions
src/agent/tools.py       -- 13 chat agent tools
src/agent/chat.py        -- Chat agent orchestration
src/web/app.py           -- FastAPI server (30+ endpoints)
src/web/static/app.js    -- Frontend JS (~2500 lines)
src/web/static/style.css -- Dark theme CSS (~2000 lines)
prompts/                 -- 17 prompt templates
```
