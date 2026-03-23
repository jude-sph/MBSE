# Project Workspace -- Design Specification

## Overview

Evolve the MBSE Model Generator from a single-shot generator into a persistent project workspace. Engineers work on requirements in small batches (1-10 at a time), grouped by capability or system. Each batch extends the existing model rather than starting from scratch. The LLM sees the current model state when generating new elements, so it reuses existing entities and integrates new elements naturally.

This addresses the real engineering workflow: an engineer receives thousands of requirements, groups them offline by subject/system, processes them through reqdecomp for decomposition, then feeds small batches into the MBSE app to build up a cumulative model over days or weeks.

## Project File

The project persists as `project.json` in the working directory (where the engineer runs `mbsegen --web`). It extends the existing `MBSEModel` structure with project metadata and batch history.

### Structure

```json
{
  "project": {
    "name": "PIB Icebreaker",
    "created_at": "2026-03-23T05:00:00Z",
    "last_modified": "2026-03-24T14:30:00Z"
  },
  "batches": [
    {
      "id": "batch-001",
      "timestamp": "2026-03-23T05:15:00Z",
      "source_file": "SAR-requirements.xlsx",
      "requirement_ids": ["REQ-SAR-001", "REQ-SAR-004", "REQ-SAR-007"],
      "layers_generated": ["operational_analysis", "system_analysis"],
      "model": "deepseek/deepseek-chat-v3-0324",
      "cost": 0.0542
    }
  ],
  "meta": {
    "source_file": "project",
    "mode": "capella",
    "selected_layers": ["operational_analysis", "system_analysis"],
    "generated_at": "2026-03-24T14:30:00Z",
    "llm_provider": "openrouter",
    "llm_model": "deepseek/deepseek-chat-v3-0324",
    "cost": null
  },
  "requirements": [],
  "layers": {},
  "links": [],
  "instructions": { "tool": "Capella 7.0", "steps": [] }
}
```

### Lifecycle

- **App start:** If `project.json` exists in the working directory, load it and render the model. If not, show empty state.
- **Auto-save:** After every batch run, inline edit, or chat agent change, `project.json` is written to disk.
- **New project:** Clears the current project (with confirmation) and starts a fresh `project.json`.
- **Single project at a time:** One active project per working directory. Designed so a project switcher can be added later without structural changes.

## Context-Aware Pipeline

When processing a new batch, the pipeline feeds the existing model into each LLM prompt so the model generates elements that integrate with what already exists.

### Stage 1: Analyze

No change. Analyzes only the new batch requirements for ambiguity.

### Stage 2: Clarify

No change. Applies clarifications to the new batch only.

### Stage 3: Generate (modified)

Each layer prompt receives two new sections:

- `{existing_elements}` -- A compact summary of existing elements in that layer (IDs and names only, not full details). Example:
  ```
  Existing elements in this layer (DO NOT recreate these, reference by ID):
  - OE-001: PIB Icebreaker (OperationalEntity, actors: CO, Nav Officer)
  - OE-002: JRCC Halifax (OperationalEntity, actors: SAR Coordinator)
  - OC-001: Conduct SAR (OperationalCapability, involves: OE-001, OE-002)
  ```

- `{requirements}` -- The new batch requirements only.

The prompt instruction changes to: "Generate NEW elements for the requirements below. Reuse existing elements by referencing their IDs where appropriate. Do NOT regenerate or duplicate existing elements. Only output new elements."

After generation, new elements are appended to the existing layer data. Element IDs must not collide with existing ones -- the prompt should instruct the LLM to continue the numbering sequence (e.g., if OE-004 exists, start at OE-005).

### Stage 4: Link (modified)

Receives both existing links and new elements. Generates links for new elements only, but can link new elements to existing ones (e.g., a new function `satisfies` an existing requirement from a previous batch, or a new activity `involves` an existing entity).

The prompt includes: existing links summary, all elements (existing + new), new requirements only.

### Stage 5: Instruct (modified)

Regenerates instructions for the entire accumulated model since recreation steps need to cover all elements. This runs on the full model after merging, not just the new batch.

### Post-Generation Merge

After the pipeline completes for a new batch:
1. New requirements are appended to `project.requirements`
2. New elements are appended to each layer's collections
3. New links are appended to `project.links`
4. Instructions are replaced with the newly generated full-model instructions
5. A batch record is added to `project.batches`
6. `project.json` is saved to disk

## Batch History

Each batch is recorded with:
- `id` -- unique identifier (e.g., "batch-001", auto-incrementing)
- `timestamp` -- when the batch was processed
- `source_file` -- the uploaded filename
- `requirement_ids` -- which requirements were in this batch
- `layers_generated` -- which layers were selected for this batch
- `model` -- which LLM model was used
- `cost` -- total cost of this batch's pipeline run

This allows the engineer to see the model's evolution: what was added when, from which source, at what cost.

## UI Changes

### Top Bar

- Project name displayed (editable inline, defaults to "Untitled Project")
- Last modified timestamp
- "New Project" button (with confirmation if current project has data)

### Left Panel

- "Generate Model" button text changes to "Add Batch"
- All other controls remain the same (mode toggle, layer selection, file upload, provider selector, requirement preview)
- The mode toggle is set once on project creation and locked for the project's lifetime (can't mix Capella and Rhapsody in one project)

### Right Panel -- Batch History Tab

New tab alongside Model Tree, Links, Instructions, Raw JSON. Shows:
- Timeline of batches, newest first
- Each batch card shows: timestamp, source filename, requirement count, layers generated, model used, cost
- Click a batch to highlight which elements in the tree came from that batch (optional enhancement)

### Model Tree

- Elements from the latest batch could have a subtle "new" indicator (small dot or highlight) that fades after the next batch. Optional polish.

### Empty State

When no project exists: centered message "No project yet. Upload requirements and add your first batch to start building a model."

### Export

Exports the entire accumulated project model. Filename uses project name: `pib-icebreaker-capella-20260324-1430.xlsx`.

## Future Reqdecomp Integration

Not built now, but the design keeps the path open:

- `Requirement` model (id, text, source_dig) matches reqdecomp output format
- Batch `source_file` field could become `source: "reqdecomp:job-abc123"` for cross-app references
- `/run` endpoint already accepts `selected_requirements` as IDs -- future integration would POST IDs directly from reqdecomp's output
- No structural changes needed to support this later

## What Does NOT Change

- LLM provider architecture (Anthropic, OpenRouter, Local)
- Model catalogue and pricing
- Cost tracking and JSONL logging
- Inline editing and chat agent tools
- Export formats (JSON, XLSX, Text)
- Git-based update mechanism
- All existing tests (this is additive, not a rewrite)
