# Full Arcadia Process Expansion -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Capella option from ~1/3 to the full 5-stage Arcadia process with all element types, a new EPBS layer, and prompts grounded in the Arcadia Data Model reference.

**Architecture:** Enrich `capella.py` with ~25 new Pydantic model classes across 5 stages. Rewrite 4 existing Capella generate prompts and add 1 new EPBS prompt. Update config with EPBS layer and SA rename. All changes are additive -- the pipeline, UI, export, and chat agent already handle arbitrary layers and collections dynamically.

**Tech Stack:** Same as existing (Python/Pydantic, prompt templates). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-23-full-arcadia-process-design.md`

**Reference docs (read before writing prompts):**
- `/new-info/Arcadia Reference - Data Model_copy.pdf` -- exact element type definitions
- `/new-info/Capella_User_Manual.pdf` -- Capella menu paths for instruct prompt
- Engineer's email in spec overview -- the 5 stages and their diagram outcomes

---

## File Map

```
Modified files:
├── src/models/capella.py          # Add ~25 new Pydantic classes, expand layer models
├── src/config.py                  # Add EPBS layer, rename SA key
├── src/stages/generate.py         # Add EPBS to PROMPT_MAP, add backward compat alias
├── src/exporter.py                # Add "system_needs_analysis" to display names
├── src/agent/tools.py             # Update example layer key in add_element description
├── src/project.py                 # Add backward compat layer key migration on load
├── prompts/generate_capella_oa.txt   # Rewrite with full OA schema (10 collections)
├── prompts/generate_capella_sa.txt   # Rewrite with full SA schema (10 collections)
├── prompts/generate_capella_la.txt   # Rewrite with full LA schema (10 collections)
├── prompts/generate_capella_pa.txt   # Rewrite with full PA schema (12 collections)
├── prompts/generate_capella_epbs.txt # NEW: EPBS schema (2 collections)
├── prompts/instruct_capella.txt      # Rewrite with all element types + correct Capella menu paths
├── prompts/link.txt                  # Update valid link types for new element types
├── tests/test_models.py              # Add tests for new Capella models
├── tests/test_pipeline.py            # Update system_analysis → system_needs_analysis
└── tests/test_stages.py              # Add test for EPBS generate
```

---

### Task 1: Expand Capella Data Model

**Files:**
- Modify: `src/models/capella.py`
- Modify: `tests/test_models.py`

This is the largest single task. Add all ~25 new Pydantic model classes and expand the 4 existing layer models + add the EPBS layer model.

- [ ] **Step 1: Write tests for new model classes**

Add to `tests/test_models.py`:

```python
# Test new OA elements
from src.models.capella import (
    OperationalProcess, OperationalInteraction, CommunicationMean,
    OperationalData, InteractionItem, OperationalModeState,
    # SA elements
    SystemDefinition, ExternalActor, SpecifiedCapability,
    SystemFunctionalChain, SpecifiedScenario, SpecifiedData,
    SystemExchangedItem, SystemModeState,
    # LA elements
    NotionalCapability, LogicalFunctionalChain, NotionalScenario,
    LogicalFunctionalExchange, LogicalExchangedItem,
    LogicalComponentExchange, LogicalInterface, LogicalModeState,
    # PA elements
    DesignedCapability, PhysicalFunctionalChain, DesignScenario,
    PhysicalFunctionalExchange, PhysicalExchangedItem,
    PhysicalComponentExchange, HostingComponent, DesignedInterface,
    PhysicalModeState,
    # EPBS elements
    ConfigurationItem, PBSNode,
)


def test_operational_process():
    p = OperationalProcess(id="OP-001", name="SAR Process", capability_ref="OC-001", activity_refs=["OA-001"])
    assert p.capability_ref == "OC-001"


def test_communication_mean():
    cm = CommunicationMean(id="CM-001", name="VHF Radio Link", source_entity="OE-001", target_entity="OE-002")
    assert cm.source_entity == "OE-001"


def test_operational_mode_state():
    ms = OperationalModeState(id="OMS-001", name="Standby", type="State", transitions=[{"target": "OMS-002", "trigger": "Alert"}])
    assert ms.type == "State"


def test_system_definition():
    s = SystemDefinition(id="SYS-001", name="PIB Icebreaker", description="Coast Guard Icebreaker")
    assert s.name == "PIB Icebreaker"


def test_specified_capability():
    sc = SpecifiedCapability(id="SC-001", name="Station Keeping", involved_functions=["SF-001"], involved_chains=["SFC-001"])
    assert len(sc.involved_functions) == 1


def test_logical_functional_chain():
    lfc = LogicalFunctionalChain(id="LFC-001", name="Propulsion Chain", function_refs=["LF-001"], exchange_refs=["LFE-001"])
    assert len(lfc.function_refs) == 1


def test_hosting_component():
    hc = HostingComponent(id="HC-001", name="Bridge Console", hosted_components=["PC-001", "PC-002"])
    assert len(hc.hosted_components) == 2


def test_configuration_item():
    ci = ConfigurationItem(id="CI-001", name="Propulsion Control Unit", type="HW", description="Main engine controller", physical_component_refs=["PC-001"])
    assert ci.type == "HW"


def test_pbs_node():
    node = PBSNode(id="PBS-001", name="Propulsion System", parent_id=None, children_ids=["PBS-002"], ci_ref="CI-001")
    assert node.ci_ref == "CI-001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`

- [ ] **Step 3: Implement all new model classes in capella.py**

Add to each section of `src/models/capella.py`:

**OA section (add after OperationalActivity):**
- `OperationalProcess`: id, name, capability_ref (str), activity_refs (list[str])
- `OperationalInteraction`: id, name, source_entity (str), target_entity (str), exchanged_items (list[str])
- `CommunicationMean`: id, name, source_entity (str), target_entity (str)
- `OperationalData`: id, name, description (str = "")
- `InteractionItem`: id, name, description (str = "")
- `OperationalModeState`: id, name, type (str, default "State"), transitions (list[dict])

Update `OperationalAnalysisLayer` to add 6 new collections:
```python
class OperationalAnalysisLayer(BaseModel):
    entities: list[OperationalEntity] = Field(default_factory=list)
    capabilities: list[OperationalCapability] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    activities: list[OperationalActivity] = Field(default_factory=list)
    operational_processes: list[OperationalProcess] = Field(default_factory=list)
    operational_interactions: list[OperationalInteraction] = Field(default_factory=list)
    communication_means: list[CommunicationMean] = Field(default_factory=list)
    operational_data: list[OperationalData] = Field(default_factory=list)
    interaction_items: list[InteractionItem] = Field(default_factory=list)
    modes_and_states: list[OperationalModeState] = Field(default_factory=list)
```

**SA section -- rename header to "System Needs Analysis", add after SystemFunctionalExchange:**
- `SystemDefinition`: id, name, description (str = "")
- `ExternalActor`: id, name, type (str, default "System")
- `SpecifiedCapability`: id, name, involved_functions (list[str]), involved_chains (list[str])
- `SystemFunctionalChain`: id, name, function_refs (list[str]), exchange_refs (list[str])
- `SpecifiedScenario`: id, name, steps (list[ScenarioStep]) -- reuse existing ScenarioStep
- `SpecifiedData`: id, name, description (str = "")
- `SystemExchangedItem`: id, name, description (str = "")
- `SystemModeState`: id, name, type (str), transitions (list[dict])

Rename `SystemAnalysisLayer` → `SystemNeedsAnalysisLayer` and add 8 new collections.

**LA section -- add after LogicalFunction:**
- `NotionalCapability`: id, name, involved_functions (list[str]), involved_chains (list[str])
- `LogicalFunctionalChain`: id, name, function_refs (list[str]), exchange_refs (list[str])
- `NotionalScenario`: id, name, steps (list[ScenarioStep])
- `LogicalFunctionalExchange`: id, name, source_function (str), target_function (str), exchanged_items (list[str])
- `LogicalExchangedItem`: id, name, description (str = "")
- `LogicalComponentExchange`: id, name, source_component (str), target_component (str)
- `LogicalInterface`: id, name, component_exchange_ref (str), exchange_items (list[str])
- `LogicalModeState`: id, name, type (str), transitions (list[dict])

Update `LogicalArchitectureLayer` to add 8 new collections.

**PA section -- add after PhysicalLink:**
- `DesignedCapability`: id, name, involved_functions (list[str]), involved_chains (list[str])
- `PhysicalFunctionalChain`: id, name, function_refs (list[str]), exchange_refs (list[str])
- `DesignScenario`: id, name, steps (list[ScenarioStep])
- `PhysicalFunctionalExchange`: id, name, source_function (str), target_function (str), exchanged_items (list[str])
- `PhysicalExchangedItem`: id, name, description (str = "")
- `PhysicalComponentExchange`: id, name, source_component (str), target_component (str)
- `HostingComponent`: id, name, hosted_components (list[str])
- `DesignedInterface`: id, name, component_exchange_ref (str), exchange_items (list[str])
- `PhysicalModeState`: id, name, type (str), transitions (list[dict])

Update `PhysicalArchitectureLayer` to add 9 new collections.

**NEW EPBS section:**
- `ConfigurationItem`: id, name, type (str, default "HW"), description (str = ""), physical_component_refs (list[str])
- `PBSNode`: id, name, parent_id (str | None = None), children_ids (list[str]), ci_ref (str = "")
- `EPBSLayer(BaseModel)`: configuration_items (list[ConfigurationItem]), pbs_structure (list[PBSNode])

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`

- [ ] **Step 6: Commit**

```bash
git add src/models/capella.py tests/test_models.py
git commit -m "feat: expand Capella data model with full Arcadia element types + EPBS"
```

---

### Task 2: Config, Backward Compat & Code Updates

**Files:**
- Modify: `src/config.py`
- Modify: `src/stages/generate.py`
- Modify: `src/exporter.py`
- Modify: `src/agent/tools.py`
- Modify: `src/project.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_stages.py`

- [ ] **Step 1: Update config.py**

Replace `CAPELLA_LAYERS`:

```python
CAPELLA_LAYERS = {
    "operational_analysis": "Operational Analysis (OA)",
    "system_needs_analysis": "System Needs Analysis (SA)",
    "logical_architecture": "Logical Architecture (LA)",
    "physical_architecture": "Physical Architecture (PA)",
    "epbs": "End-Product Breakdown Structure (EPBS)",
}
```

- [ ] **Step 2: Update generate.py PROMPT_MAP**

```python
PROMPT_MAP = {
    ("capella", "operational_analysis"): "generate_capella_oa.txt",
    ("capella", "system_needs_analysis"): "generate_capella_sa.txt",
    ("capella", "system_analysis"): "generate_capella_sa.txt",  # backward compat
    ("capella", "logical_architecture"): "generate_capella_la.txt",
    ("capella", "physical_architecture"): "generate_capella_pa.txt",
    ("capella", "epbs"): "generate_capella_epbs.txt",
    # Rhapsody entries unchanged...
}
```

- [ ] **Step 3: Update exporter.py display names**

Add to `_LAYER_DISPLAY_NAMES`:
```python
"system_needs_analysis": "System Needs Analysis",
"epbs": "End-Product Breakdown Structure",
```

- [ ] **Step 4: Update agent/tools.py**

Find the `add_element` tool description that references `'system_analysis'` and change to `'system_needs_analysis'`. Also add `'epbs'` to the example list.

- [ ] **Step 5: Add backward compat migration to project.py**

In `load_project()`, after loading the project, migrate old layer keys:
```python
def load_project(path=None):
    ...
    project = ProjectModel.model_validate(data)
    # Migrate old layer keys
    if "system_analysis" in project.layers and "system_needs_analysis" not in project.layers:
        project.layers["system_needs_analysis"] = project.layers.pop("system_analysis")
    return project
```

- [ ] **Step 6: Update test_pipeline.py**

Change `"system_analysis"` → `"system_needs_analysis"` in the test that uses `selected_layers`.

- [ ] **Step 7: Add EPBS generate test to test_stages.py**

```python
def test_generate_epbs_returns_valid_structure(sample_requirements):
    mock_response = {
        "configuration_items": [
            {"id": "CI-001", "name": "Engine Control Unit", "type": "HW", "description": "Main controller", "physical_component_refs": ["PC-001"]}
        ],
        "pbs_structure": [
            {"id": "PBS-001", "name": "Propulsion System", "parent_id": None, "children_ids": [], "ci_ref": "CI-001"}
        ],
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("capella", "epbs", sample_requirements, tracker)
    assert "configuration_items" in result
    assert result["configuration_items"][0]["type"] == "HW"
```

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ -v`

- [ ] **Step 9: Commit**

```bash
git add src/config.py src/stages/generate.py src/exporter.py src/agent/tools.py src/project.py tests/test_pipeline.py tests/test_stages.py
git commit -m "feat: add EPBS layer, rename SA, backward compat aliases"
```

---

### Task 3: Rewrite Capella Generate Prompts

**Files:**
- Rewrite: `prompts/generate_capella_oa.txt`
- Rewrite: `prompts/generate_capella_sa.txt`
- Rewrite: `prompts/generate_capella_la.txt`
- Rewrite: `prompts/generate_capella_pa.txt`
- Create: `prompts/generate_capella_epbs.txt`

This is the most important task for output quality. Each prompt must be rewritten to include all Arcadia element types with exact definitions from the Data Model reference.

**CRITICAL:** Read the reference documents before writing prompts:
- `/new-info/Arcadia Reference - Data Model_copy.pdf` -- sections 4.1.1 (OA), 4.1.2 (SA), 4.2.1 (LA), 4.2.2 (PA), 4.2.3 (PBS)
- The engineer specifically noted "Gemini completely got wrong as it kept hallucinating menu items" -- prompts must use exact Arcadia terminology

- [ ] **Step 1: Rewrite generate_capella_oa.txt**

Structure:
1. "You are generating Arcadia Operational Analysis elements for Capella."
2. Purpose: "Operational Analysis identifies what system users need to accomplish -- their goals, activities, and interactions -- without defining the system itself."
3. Element definitions (from Data Model ref section 4.1.1):
   - Operational Entities/Actors: "A real world entity or stakeholder involved in a mission. An actor is a [usually human] non decomposable operational Entity."
   - Users Missions & Capabilities: "A mission is a major goal to which the system is expected to contribute. A capability is the ability of an operational entity to provide a service."
   - Operational Activities: "An action, operation or service fulfilled by an operational entity, contributing to a mission."
   - Operational Processes: "A logical organization of Interactions and Activities to fulfil an Operational Capability."
   - Operational Scenarios: "A time-ordered set of interactions between operational activities performed by operational entities to fulfil an Operational Capability."
   - Operational Interactions: "Exchanges conveyed through communication links between operational entities or actors."
   - Communication Means: "A medium enabling interactions between entities and actors."
   - Operational Data: "Elements of interactions or communications between entities or actors."
   - Interaction Items: "What is expected to be exchanged by the entities and activities."
   - Modes & States: "An automaton describing how modes & states are linked by transitions."
4. JSON output schema with all 10 collections and field definitions
5. `{{existing_elements}}` and `{{requirements}}` placeholders
6. Rules: exact Arcadia terminology, unique IDs with prefixes (OE-, OC-, OA-, OP-, OI-, CM-, OD-, II-, OMS-)

- [ ] **Step 2: Rewrite generate_capella_sa.txt**

Same structure for System Needs Analysis. Element definitions from section 4.1.2:
- System Definition, External Actors, Specified Capabilities, System Functions, Functional Chains, Specified Scenarios, Specified Functional Exchanges, Specified Data, Exchanged Items, Modes & States
- ID prefixes: SYS-, EA-, SC-, SF-, SFC-, SS-, SFE-, SD-, SEI-, SMS-

- [ ] **Step 3: Rewrite generate_capella_la.txt**

Same structure for Logical Architecture. Element definitions from section 4.2.1:
- Logical Components, Logical Functions, Notional Capabilities, Functional Chains, Notional Scenarios, Functional Exchanges, Exchanged Items, Component Exchanges, Interfaces, Modes & States
- ID prefixes: LC-, LF-, NC-, LFC-, NS-, LFE-, LEI-, LCE-, LI-, LMS-

- [ ] **Step 4: Rewrite generate_capella_pa.txt**

Same structure for Physical Architecture. Element definitions from section 4.2.2:
- Physical Components, Physical Functions, Physical Links, Designed Capabilities, Functional Chains, Design Scenarios, Functional Exchanges, Exchanged Items, Component Exchanges, Hosting Components, Designed Interfaces, Modes & States
- ID prefixes: PC-, PF-, PL-, DC-, PFC-, DS-, PFE-, PEI-, PCE-, HC-, DI-, PMS-

- [ ] **Step 5: Create generate_capella_epbs.txt**

New prompt for EPBS. Element definitions from section 4.2.3:
- Configuration Items: "Any hardware, software, or combination of both that satisfies an end use function and is designated for separate configuration management."
- PBS Structure: "The Organisation of the System-of-Interest (end products components) in a tree frame."
- ID prefixes: CI-, PBS-
- The prompt should reference the physical architecture layer's components to derive configuration items from them.

- [ ] **Step 6: Run test suite to ensure prompt placeholders work**

Run: `pytest tests/test_stages.py -v`
(The mock-based tests verify prompts load and format without errors)

- [ ] **Step 7: Commit**

```bash
git add prompts/generate_capella_*.txt
git commit -m "feat: rewrite Capella generate prompts with full Arcadia element types"
```

---

### Task 4: Rewrite Capella Instruct Prompt & Link Prompt

**Files:**
- Rewrite: `prompts/instruct_capella.txt`
- Modify: `prompts/link.txt`

- [ ] **Step 1: Rewrite instruct_capella.txt**

The instruct prompt must cover all element types across all 5 stages and reference correct Capella menu paths from the User Manual (section 14: Properties, section 7: Diagram Management).

Key menu paths from the Capella User Manual:
- Operational Analysis: Properties section 14.1-14.6
- System Analysis: Properties section 14.13-14.15
- Logical Architecture: Properties section 14.16-14.18
- Physical Architecture: Properties section 14.19-14.24
- EPBS: Properties section 14.25 (Configuration Items)
- Diagram types: section 7.2 (Class, Mode State, Breakdown, Dataflow, Architecture, Interface, Scenarios)

Update the valid layer enumeration to include `epbs` and use `system_needs_analysis`.

- [ ] **Step 2: Update link.txt**

The link prompt's valid link types should include types relevant to the new element types:
- Add: `realizes` (LA function realizes SA function), `implements` (PA component implements LA component), `allocates` (function allocated to component), `communicates` (via communication means)
- Ensure the prompt can link elements across all 5 stages

- [ ] **Step 3: Run test suite**

Run: `pytest tests/ -v`

- [ ] **Step 4: Commit**

```bash
git add prompts/instruct_capella.txt prompts/link.txt
git commit -m "feat: rewrite instruct and link prompts for full Arcadia process"
```

---

### Task 5: Integration Test & Push

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Verify server starts**

Run: `python3 -c "from src.web.app import app; print('OK')"`

- [ ] **Step 3: Verify EPBS appears in UI**

Start server briefly, check that the layer checkboxes include "End-Product Breakdown Structure (EPBS)".

- [ ] **Step 4: Commit any final fixes**

- [ ] **Step 5: Push to GitHub**

```bash
git push
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Expand Capella data model (~25 new classes) | src/models/capella.py |
| 2 | Config, backward compat, code updates | config.py, generate.py, exporter.py, tools.py, project.py |
| 3 | Rewrite 4 + create 1 Capella generate prompts | prompts/generate_capella_*.txt |
| 4 | Rewrite instruct + update link prompts | prompts/instruct_capella.txt, link.txt |
| 5 | Integration test + push | Tests, server check, git push |
