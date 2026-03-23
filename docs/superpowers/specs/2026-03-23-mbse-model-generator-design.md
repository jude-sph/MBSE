# MBSE Model Generator -- Design Specification

## Overview

A web application that transforms pre-decomposed textual requirements into Model-Based Systems Engineering (MBSE) model structures for two target tools: Capella (Arcadia methodology) and IBM Rhapsody (SysML notation). Engineers upload requirements from the reqdecomp tool, select their target modeling tool and desired architecture layers, and receive a hierarchical model structure with element linking and step-by-step recreation instructions.

The app is NOT about designing ships -- it defines how vessels achieve their missions by modeling the operational reality first, then working toward physical architecture. A single compound requirement like DIG-5967 (SAR Keep Station) gets decomposed upstream by reqdecomp, then this tool transforms those decomposed requirements (REQ-SAR-001 through 007) into traceable MBSE model elements across Arcadia or SysML layers.

## Architecture

### High-Level Data Flow

```
Input (XLSX/CSV)  -->  Pipeline (5 stages)  -->  Output (Tree + Export)
     |                      |                         |
  Config:               LLM calls:              Refinement:
  - Mode toggle         - Local (<=3B)          - Inline editing (small)
  - Layer select         or OpenRouter          - Chat agent w/ tools (big)
  - LLM provider
```

### Tech Stack

Follows the reqdecomp project patterns:

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic 2.0+, openpyxl, python-dotenv, httpx
- **Frontend:** Vanilla JavaScript (no frameworks, no build step), Jinja2 templates
- **Real-time:** Server-Sent Events (SSE) for pipeline progress
- **LLM:** Dual provider -- Anthropic (direct) and OpenRouter (OpenAI-compatible client)
- **Deployment:** Python package with `pip install -e .`, CLI entry point `mbsegen --web`

### Project Structure

```
MBSE/
  src/
    __init__.py
    main.py              # CLI entry point
    config.py             # Paths, API keys, model catalogue, pricing
    llm_client.py         # Unified provider client (Anthropic + OpenRouter)
    cost_tracker.py       # Token/cost accounting
    parser.py             # XLSX/CSV requirement file parsing
    pipeline.py           # 5-stage generation pipeline orchestration
    stages/
      __init__.py
      analyze.py          # Stage 1: requirement analysis + ambiguity detection
      clarify.py          # Stage 2: structured clarification Q&A
      generate.py         # Stage 3: layer-by-layer model generation
      link.py             # Stage 4: cross-element relationship generation
      instruct.py         # Stage 5: tool-specific recreation instructions
    models/
      __init__.py
      core.py             # Pydantic models: MBSEModel, Layer, Element, Link, etc.
      capella.py           # Arcadia-specific element types and link types
      rhapsody.py          # SysML-specific element types and link types
    agent/
      __init__.py
      chat.py             # Chat agent orchestration
      tools.py            # Agent tool definitions (add/modify/remove elements & links)
    web/
      app.py              # FastAPI server, all endpoints
      templates/
        index.html        # Main page (Jinja2)
      static/
        app.js            # All frontend interactivity
        style.css          # Dark theme styling
  prompts/
    analyze.txt           # Stage 1 prompt template
    clarify.txt           # Stage 2 prompt template
    generate_capella_oa.txt  # Stage 3: Capella Operational Analysis
    generate_capella_sa.txt  # Stage 3: Capella System Analysis
    generate_capella_la.txt  # Stage 3: Capella Logical Architecture
    generate_capella_pa.txt  # Stage 3: Capella Physical Architecture
    generate_rhapsody_req.txt  # Stage 3: Rhapsody Requirements Diagram
    generate_rhapsody_bdd.txt  # Stage 3: Rhapsody Block Definition
    generate_rhapsody_ibd.txt  # Stage 3: Rhapsody Internal Block
    generate_rhapsody_act.txt  # Stage 3: Rhapsody Activity Diagram
    generate_rhapsody_seq.txt  # Stage 3: Rhapsody Sequence Diagram
    generate_rhapsody_stm.txt  # Stage 3: Rhapsody State Machine
    link.txt              # Stage 4 prompt template
    instruct_capella.txt  # Stage 5: Capella-specific instructions
    instruct_rhapsody.txt # Stage 5: Rhapsody-specific instructions
    agent_system.txt      # Chat agent system prompt
  scripts/
    start.sh              # Start web server
  .env                    # API keys and configuration
  .env.example            # Template for .env
  pyproject.toml          # Package metadata and dependencies
  requirements.txt        # Plain dependency list
  .gitignore
```

## Core Data Model

The pipeline output is a structured JSON model. Every element has a unique ID to enable inline editing and agent tool operations.

### MBSEModel (top-level)

```json
{
  "meta": {
    "source_file": "SAR-requirements.xlsx",
    "mode": "capella",
    "selected_layers": ["operational_analysis", "system_analysis"],
    "generated_at": "2026-03-23T14:30:00Z",
    "llm_provider": "openrouter",
    "llm_model": "anthropic/claude-sonnet-4",
    "cost": {
      "total_input_tokens": 24800,
      "total_output_tokens": 16400,
      "estimated_cost": 0.089,
      "calls": [
        {"stage": "analyze", "input_tokens": 3200, "output_tokens": 1800, "cost": 0.012}
      ]
    }
  },
  "requirements": [
    {
      "id": "REQ-SAR-001",
      "text": "The crew shall monitor GMDSS frequencies (VHF Ch 16/70, MF 2182 kHz).",
      "source_dig": "DIG-5967"
    }
  ],
  "layers": {
    "operational_analysis": {
      "entities": [...],
      "capabilities": [...],
      "scenarios": [...],
      "activities": [...]
    },
    "system_analysis": {
      "functions": [...],
      "exchanges": [...]
    },
    "logical_architecture": {
      "components": [...],
      "interfaces": [...]
    },
    "physical_architecture": {
      "nodes": [...],
      "deployments": [...]
    }
  },
  "links": [
    {
      "id": "LNK-001",
      "source": "OA-003",
      "target": "REQ-SAR-004",
      "type": "satisfies",
      "description": "Maintain Station activity satisfies the 10m radius station-keeping requirement"
    }
  ],
  "instructions": {
    "tool": "Capella 7.0",
    "steps": [
      {
        "step": 1,
        "action": "Create a new Capella project",
        "detail": "File > New > Capella Project. Name it matching your program identifier.",
        "layer": "general"
      }
    ]
  }
}
```

### Capella/Arcadia Element Types

For Operational Analysis (OA):
- **OEBD elements:** OperationalEntity (with actors), OperationalActor
- **OCB elements:** OperationalCapability, EntityInvolvement
- **OES elements:** Scenario, ScenarioStep (from, to, message, sequence)
- **OAB elements:** OperationalActivity, FunctionalExchange, EntityRole

For System Analysis (SA):
- **SAB elements:** SystemFunction, FunctionalExchange, SystemActor

For Logical Architecture (LA):
- **LAB elements:** LogicalComponent, LogicalFunction, FunctionalExchange, ComponentExchange

For Physical Architecture (PA):
- **PAB elements:** PhysicalComponent, PhysicalFunction, PhysicalLink, NodeDeployment

### Arcadia Link Types
- `satisfies` -- function/activity satisfies a requirement
- `realizes` -- lower-layer element realizes upper-layer element
- `implements` -- physical component implements logical component
- `involves` -- entity is involved in capability
- `exchanges` -- functional exchange between activities/functions

### Rhapsody/SysML Element Types

Per ISO/IEC/IEEE 24641:2023:
- **Requirements Diagram:** Requirement (id, text, priority, status)
- **Block Definition Diagram (BDD):** Block, ValueProperty, FlowPort, ProxyPort
- **Internal Block Diagram (IBD):** Part, Connector, FlowPort binding
- **Activity Diagram:** Action, ObjectFlow, ControlFlow, Pin
- **Sequence Diagram:** Lifeline, Message, CombinedFragment
- **State Machine Diagram:** State, Transition, Trigger, Guard

### SysML Link Types
- `deriveReqt` -- requirement derives from another
- `satisfy` -- block/function satisfies requirement
- `refine` -- element refines requirement
- `trace` -- traceability link
- `allocate` -- function allocated to block

## Pipeline Stages

### Stage 1: Analyze

Parses the uploaded XLSX/CSV file, extracts each requirement into the data model's `requirements` array. Sends requirements to the LLM with the analysis prompt template. The LLM identifies:
- Ambiguous or incomplete requirements
- Missing context that would affect model accuracy
- Requirements that may need splitting further

Returns a list of flagged requirements with specific clarification questions.

### Stage 2: Clarify (conditional)

Only runs if Stage 1 flagged issues. Presents questions to the user as a structured form in the UI -- each question shows the flagged requirement text, the specific issue, and a text input for the user's response. The user answers and clicks "Continue." Not a free-form chat -- targeted Q&A.

If no issues were flagged, this stage is skipped automatically.

### Stage 3: Generate (layer-by-layer)

The core generation stage. For each user-selected layer, a separate LLM call is made using a layer-specific prompt template. Each prompt includes:
- The full set of (clarified) requirements
- The schema for that layer's element types
- An in-context example showing expected output structure
- The target notation (Arcadia or SysML)

Prompts are designed for quality first -- as large as needed for accurate output. If a local model's context window is too small for a particular stage, the app surfaces a clear message recommending OpenRouter.

SSE events stream progress per layer so the user sees real-time updates.

### Stage 4: Link

A dedicated pass that receives all generated elements across all layers and establishes cross-references. The prompt includes the complete element list and asks the LLM to identify relationships using the correct link types for the target notation.

This stage runs after all layers are generated to ensure cross-layer traceability (e.g., a Physical component `implements` a Logical component which `realizes` a System function which `satisfies` a Requirement).

### Stage 5: Instruct

Takes the complete model and generates ordered, tool-specific recreation steps. The prompt includes:
- The target tool and version (e.g., "Capella 7.0" or "IBM Rhapsody 10.0")
- The complete model structure
- Instructions to reference actual menu paths, dialog names, and naming conventions

Output is an ordered list of steps grouped by layer, so the engineer can follow them sequentially in the modeling tool.

## Refinement: Inline Editing + Chat Agent

### Inline Editing (small changes)

The tree view supports direct manipulation:
- Click the edit icon on any element to rename it or change properties
- Click "+ Add" at the bottom of any group to add a new element
- Click the delete icon to remove an element (confirms first, cascades to remove associated links)
- Changes update the JSON model immediately and re-render the tree

### Chat Agent (structural changes)

For larger changes, a chat panel at the bottom of the output area provides an agent with tools. The agent uses OpenRouter exclusively (requires tool-calling capability).

#### Agent Tools

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `add_element` | layer, type, name, properties, parent_id? | Add a new element to a layer |
| `modify_element` | element_id, fields_to_update | Change properties of an existing element |
| `remove_element` | element_id, cascade? | Delete an element and optionally its links |
| `add_link` | source_id, target_id, link_type, description | Create a relationship |
| `modify_link` | link_id, fields_to_update | Change a link's type or description |
| `remove_link` | link_id | Delete a relationship |
| `regenerate_layer` | layer_name, additional_context? | Re-run pipeline Stage 3 for a specific layer |
| `add_instruction_step` | step_number, action, detail, layer | Insert an instruction step |
| `list_elements` | layer?, type? | Read-only: list elements with filtering |
| `list_links` | element_id? | Read-only: list links, optionally filtered by element |
| `get_element_details` | element_id | Read-only: full details of one element |

Each tool call updates the JSON model. The tree view re-renders. The agent responds with a summary of changes made.

## LLM Provider Architecture

Reuses the dual-provider architecture from the reqdecomp project.

### Providers

- **Anthropic (direct):** Uses the `anthropic` Python SDK. Supports Claude models directly.
- **OpenRouter:** Uses the `openai` Python SDK pointed at `https://openrouter.ai/api/v1`. Supports all models via a single API key.
- **Local LLM:** Uses the `openai` Python SDK pointed at a local endpoint (e.g., Ollama at `http://localhost:11434/v1`). Available for pipeline generation. Not used for the chat agent (requires tool-calling).

### Model Catalogue

Carried over from reqdecomp with the same 14 models, pricing, quality ratings, and descriptions:

| Model | Provider | Price (in/out per Mtok) | Quality | Speed |
|-------|----------|------------------------|---------|-------|
| Claude Sonnet 4.6 | Anthropic | $3 / $15 | Excellent | Medium |
| Claude Haiku 4.5 | Anthropic | $0.80 / $4 | Good | Fast |
| Claude Sonnet 4 (OR) | OpenRouter | $3 / $15 | Excellent | Medium |
| Claude Haiku 4 (OR) | OpenRouter | $0.80 / $4 | Good | Fast |
| Gemini 2.5 Flash | OpenRouter | $0.15 / $0.60 | Good | Very Fast |
| Gemini 2.5 Pro | OpenRouter | $1.25 / $10 | Very Good | Medium |
| DeepSeek V3 | OpenRouter | $0.27 / $1.10 | Good | Fast |
| DeepSeek R1 | OpenRouter | $0.55 / $2.19 | Very Good | Slow |
| GPT-4o Mini | OpenRouter | $0.15 / $0.60 | Fair | Very Fast |
| GPT-4o | OpenRouter | $2.50 / $10 | Very Good | Medium |
| Llama 4 Maverick | OpenRouter | $0.20 / $0.60 | Good | Fast |
| Qwen 3 235B (MoE) | OpenRouter | $0.20 / $0.60 | Very Good | Medium |
| Qwen 3 32B | OpenRouter | $0.10 / $0.30 | Good | Fast |
| Qwen 3 30B (3B active) | OpenRouter | $0.05 / $0.15 | Fair | Very Fast |

Each model includes detailed descriptions, pros, and cons displayed in the Settings UI, matching the reqdecomp presentation.

### LLM Client

Unified client with:
- Retry logic: 3 attempts with exponential backoff (2s, 5s, 10s)
- JSON extraction from markdown code blocks
- Cost tracking per call (actual cost from API headers or estimated from token counts)
- Reusable client instances across pipeline stages

### Cost Tracking

Each pipeline run tracks:
- Per-stage token counts (input + output)
- Per-stage cost (actual from API or estimated from MODEL_PRICING)
- Running total displayed in the UI during generation
- Final summary stored in the model's `meta.cost` field

## User Interface

### Layout

Two-panel layout:

**Left panel (320px, fixed):**
1. Mode toggle -- Capella/Arcadia vs Rhapsody/SysML (segmented control)
2. Layer/diagram selection -- checkboxes for which layers to generate
3. File upload -- drag-and-drop zone for XLSX/CSV
4. LLM provider selector -- OpenRouter / Local LLM toggle
5. Generate button -- green, prominent

**Right panel (flex):**
1. Tab bar -- Model Tree | Links | Instructions | Raw JSON | Export button
2. Model tree -- collapsible hierarchy with inline edit controls
3. Chat agent -- collapsed panel at bottom, expands on click

### Top Bar
- App name and version
- Settings button (opens modal for API keys, model selection with catalogue)
- Update button (git-based, shows commit count when updates available)

### Styling
- Dark theme matching reqdecomp: background `#0a0a12`, accent `#7c7cff`, green `#1a5a1a`/`#4ade80`
- Monospace font for element IDs and types
- Collapsible tree nodes with expand/collapse arrows
- Hover effects on interactive elements
- Toast notifications for actions (element added, link created, etc.)

### Output Tabs

**Model Tree:** Hierarchical view grouped by layer > diagram type > elements. Each element row shows: ID (muted), name, type badge, edit icon. Each section has a "Regen" button. Each group has an "+ Add" button.

**Links:** Table view of all relationships. Columns: source element, link type, target element, description. Sortable and filterable.

**Instructions:** Ordered step list grouped by layer. Each step shows: number, action (bold), detailed instructions. Copy-to-clipboard button per step.

**Raw JSON:** Syntax-highlighted JSON view of the complete model. Copy-all button.

## Cost Estimation, Tracking & Logging

### Pre-Run Cost Estimation

Before the pipeline runs, a dry-run estimation step calculates the expected cost based on:
- Number of requirements uploaded
- Number of layers selected
- Selected model's pricing (from MODEL_PRICING)
- Estimated token counts per stage (based on prompt template sizes + expected output)

This is presented as a **cost confirmation modal** before generation begins:
- Shows estimated number of LLM calls (e.g., "1 analyze + 1 clarify + 4 generate + 1 link + 1 instruct = 8 calls")
- Shows per-stage cost breakdown with the selected model's pricing
- Shows estimated total cost range (min/max based on output variability)
- Displays selected model name and provider
- "Proceed" and "Cancel" buttons

The engineer must confirm before any LLM calls are made.

### Per-Run Cost Tracking

During pipeline execution, cost is tracked in real-time:
- Each LLM call records: stage name, input tokens, output tokens, actual cost (from API headers) or estimated cost (from MODEL_PRICING fallback)
- Running total is displayed in the UI progress area during generation
- Final cost summary is stored in the model's `meta.cost` field
- Chat agent tool calls also accumulate cost, tracked separately under `meta.cost.refinement`

### Cost Log

Every pipeline run and every chat agent interaction is logged to a persistent cost log file at `output/cost_log.jsonl` (one JSON line per event):

```json
{"timestamp": "2026-03-23T14:30:00Z", "type": "pipeline_run", "source_file": "SAR-requirements.xlsx", "mode": "capella", "layers": ["operational_analysis", "system_analysis"], "model": "anthropic/claude-sonnet-4", "provider": "openrouter", "stages": [{"stage": "analyze", "input_tokens": 3200, "output_tokens": 1800, "cost": 0.012}, ...], "total_input_tokens": 24800, "total_output_tokens": 16400, "total_cost": 0.089}
{"timestamp": "2026-03-23T14:35:00Z", "type": "chat_agent", "action": "regenerate_layer", "model": "anthropic/claude-sonnet-4", "input_tokens": 5200, "output_tokens": 3100, "cost": 0.031}
```

This log persists across runs so engineers can track cumulative spend. The Settings modal includes a "Cost History" section showing:
- Total spend to date
- Spend per day/week
- Average cost per run
- Most expensive runs

## Export

The export dropdown offers:
- **JSON** -- complete model as a `.json` file
- **XLSX** -- structured workbook with sheets per layer, a links sheet, and an instructions sheet
- **Text** -- formatted plain text hierarchical list with instructions (for printing or pasting into documents)

## Deployment & Updates

### Installation

```bash
git clone https://github.com/jude-sph/MBSE.git
cd MBSE
pip install -e .
```

### Running

```bash
mbsegen --web
# Server starts on http://localhost:8000
```

### Configuration (.env)

```env
# Provider: "anthropic" or "openrouter"
PROVIDER=openrouter

# Anthropic direct
ANTHROPIC_API_KEY=sk-ant-...

# OpenRouter
OPENROUTER_API_KEY=sk-or-...

# Local LLM endpoint (optional)
LOCAL_LLM_URL=http://localhost:11434/v1

# Model (works with both providers)
MODEL=anthropic/claude-sonnet-4

# Default output mode: "capella" or "rhapsody"
DEFAULT_MODE=capella
```

### Git-Based Updates

Identical mechanism to reqdecomp:

1. **Check for updates** (`/check-updates` endpoint): runs `git fetch --quiet`, compares `git rev-list HEAD..@{u} --count`, retrieves new commit messages
2. **Install update** (`/update` endpoint): runs `git pull`, then `pip install -e . -q`
3. **UI flow:** background check on page load, pulsing banner if updates available, "Update Now" button, persistent restart notice after update installed

### Dependencies

```
fastapi>=0.115.0
uvicorn>=0.32.0
pydantic>=2.0.0
openpyxl>=3.1.0
python-dotenv>=1.0.0
httpx>=0.27.0
anthropic>=0.40.0
openai>=1.50.0
jinja2>=3.1.0
```

## GitHub Repository

Target: https://github.com/jude-sph/MBSE.git

The repository ships as a complete Python package. Engineers clone, install, configure `.env`, and run.
