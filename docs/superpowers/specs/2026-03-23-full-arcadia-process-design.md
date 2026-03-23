# Full Arcadia Process -- Design Specification

## Overview

Expand the Capella/Arcadia option in the MBSE app to cover the complete 5-stage Arcadia process as defined by the Thales Arcadia Reference Data Model. The current implementation covers roughly 1/3 of the process -- basic elements for 4 stages with many element types missing and the 5th stage (EPBS) absent entirely.

This change is Capella-only. The Rhapsody/SysML option is unaffected.

**Reference documents (in `/new-info/`):**
- Arcadia Reference: Engineering Data Model (Thales 2023) -- defines all element types and relationships
- Arcadia User Guide -- describes the 5-stage process and its outcomes
- Capella User Manual -- exact tool menu paths for recreation instructions

## What Changes

### 1. Expanded Data Model (`src/models/capella.py`)

Each Arcadia stage produces specific element types that map to diagram views ("blanks"). The data model must include all element types so the LLM can generate complete Arcadia-compliant output.

#### Stage 1: Operational Analysis (OA)

Diagrams: OEB (Entity Blank), OCB (Capability Blank), OAB (Activity Blank)

Current collections (4): entities, capabilities, scenarios, activities

**Add (6 new collections):**

| Collection | Model Class | Key Fields | Arcadia Definition |
|-----------|-------------|------------|-------------------|
| `operational_processes` | `OperationalProcess` | id, name, capability_ref, activity_refs[] | Logical organization of interactions and activities to fulfil a capability |
| `operational_interactions` | `OperationalInteraction` | id, name, source_entity, target_entity, exchanged_items[] | Exchanges conveyed through communication links between entities or actors |
| `communication_means` | `CommunicationMean` | id, name, source_entity, target_entity | Medium enabling interactions between entities and actors |
| `operational_data` | `OperationalData` | id, name, description | Elements of interactions or communications between entities or actors |
| `interaction_items` | `InteractionItem` | id, name, description | What is expected to be exchanged by entities and activities allocated to each |
| `modes_and_states` | `OperationalModeState` | id, name, type (Mode/State/Initial/Final), transitions[] | Automaton describing how modes & states are linked by transitions |

**Total: 10 collections**

#### Stage 2: System Needs Analysis (SA)

Diagrams: MCB (Mission Capability Blank), SAB (System Architecture Blank), SFBD (System Functional Breakdown Diagram)

Current collections (2): functions, exchanges

**Add (8 new collections):**

| Collection | Model Class | Key Fields | Arcadia Definition |
|-----------|-------------|------------|-------------------|
| `system` | `SystemDefinition` | id, name, description | The system-of-interest or solution to be delivered to customers |
| `external_actors` | `ExternalActor` | id, name, type (System/Human/Organization) | External entity interacting with the system via its interfaces |
| `specified_capabilities` | `SpecifiedCapability` | id, name, involved_functions[], involved_chains[] | Ability required from the system to provide a service supporting a mission |
| `functional_chains` | `SystemFunctionalChain` | id, name, function_refs[], exchange_refs[] | Logical organization of functions and exchanges to fulfil a capability |
| `specified_scenarios` | `SpecifiedScenario` | id, name, steps[] (from, to, message, sequence) | Time-ordered set of functional exchanges between functions or with actors |
| `specified_data` | `SpecifiedData` | id, name, description | Data exchanged between system and actors |
| `exchanged_items` | `SystemExchangedItem` | id, name, description | What is expected to be exchanged by the system, actors, and functions |
| `modes_and_states` | `SystemModeState` | id, name, type, transitions[] | System modes and state transitions |

**Rename:** `system_analysis` key → `system_needs_analysis` (with backward compat alias)

**Total: 10 collections**

#### Stage 3: Logical Architecture (LA)

Diagrams: LAB (Logical Architecture Blank), LFBD (Logical Functional Breakdown Diagram)

Current collections (2): components, functions

**Add (8 new collections):**

| Collection | Model Class | Key Fields | Arcadia Definition |
|-----------|-------------|------------|-------------------|
| `notional_capabilities` | `NotionalCapability` | id, name, involved_functions[], involved_chains[] | Way the system provides a service supporting the achievement of a mission |
| `functional_chains` | `LogicalFunctionalChain` | id, name, function_refs[], exchange_refs[] | Behavior of the system in a given context as a chain of functions |
| `notional_scenarios` | `NotionalScenario` | id, name, steps[] | Time-ordered exchanges between functions or with external actors |
| `functional_exchanges` | `LogicalFunctionalExchange` | id, name, source_function, target_function, exchanged_items[] | Interaction from source function to another delivering exchange items |
| `exchanged_items` | `LogicalExchangedItem` | id, name, description | What is exchanged by system, components, actors, and functions |
| `component_exchanges` | `LogicalComponentExchange` | id, name, source_component, target_component | Interaction between two logical components |
| `interfaces` | `LogicalInterface` | id, name, component_exchange_ref, exchange_items[] | Groups of exchange items allocated to component exchanges |
| `modes_and_states` | `LogicalModeState` | id, name, type, transitions[] | Logical modes linked by transitions |

**Total: 10 collections**

#### Stage 4: Physical Architecture (PA)

Diagrams: PAB (Physical Architecture Blank), PFBD (Physical Functional Breakdown Diagram)

Current collections (3): components, functions, links

**Add (9 new collections):**

| Collection | Model Class | Key Fields | Arcadia Definition |
|-----------|-------------|------------|-------------------|
| `designed_capabilities` | `DesignedCapability` | id, name, involved_functions[], involved_chains[] | Capabilities at the physical design level |
| `functional_chains` | `PhysicalFunctionalChain` | id, name, function_refs[], exchange_refs[] | Design-level function chains |
| `design_scenarios` | `DesignScenario` | id, name, steps[] | Time-ordered exchanges between components or with external actors |
| `functional_exchanges` | `PhysicalFunctionalExchange` | id, name, source_function, target_function, exchanged_items[] | Exchanges between physical functions |
| `exchanged_items` | `PhysicalExchangedItem` | id, name, description | What is exchanged |
| `component_exchanges` | `PhysicalComponentExchange` | id, name, source_component, target_component | Exchanges between physical components |
| `hosting_components` | `HostingComponent` | id, name, hosted_components[] | Physical component hosting behavioural components, delivering resources |
| `designed_interfaces` | `DesignedInterface` | id, name, component_exchange_ref, exchange_items[] | Physical interfaces |
| `modes_and_states` | `PhysicalModeState` | id, name, type, transitions[] | Design modes |

**Total: 12 collections**

#### Stage 5: EPBS (NEW)

Diagram: PBS (Product Breakdown Structure)

| Collection | Model Class | Key Fields | Arcadia Definition |
|-----------|-------------|------------|-------------------|
| `configuration_items` | `ConfigurationItem` | id, name, type (COTS/CS/HW/Interface/ND/PrimeItem/System), description, physical_component_refs[] | Hardware, software, or combination designated for separate configuration management |
| `pbs_structure` | `PBSNode` | id, name, parent_id, children_ids[], ci_ref | Hierarchical parent-child breakdown of configuration items |

**Total: 2 collections**

### 2. Config Changes (`src/config.py`)

```python
CAPELLA_LAYERS = {
    "operational_analysis": "Operational Analysis (OA)",
    "system_needs_analysis": "System Needs Analysis (SA)",
    "logical_architecture": "Logical Architecture (LA)",
    "physical_architecture": "Physical Architecture (PA)",
    "epbs": "End-Product Breakdown Structure (EPBS)",
}
```

### 3. Backward Compatibility

Existing projects with `system_analysis` layer key must still work. Two places need aliases:

- `generate.py` PROMPT_MAP: add `("capella", "system_analysis")` pointing to the same prompt
- `project.py` or `pipeline.py`: when loading a project, map `system_analysis` → `system_needs_analysis` in the layers dict
- `agent/tools.py`: update the `add_element` tool description which hardcodes `'system_analysis'` as an example layer key -- change to `'system_needs_analysis'`
- `exporter.py`: add `"system_needs_analysis": "System Needs Analysis"` to `_LAYER_DISPLAY_NAMES`
- `instruct_capella.txt`: update the valid layer enumeration to include `epbs` and replace `system_analysis` with `system_needs_analysis`
- `tests/test_pipeline.py`: existing test uses `system_analysis` which will work via backward compat alias, but update to `system_needs_analysis` for clarity

### 4. Prompt Templates

#### Generate prompts (5 files)

Each prompt is rewritten to include:
1. Arcadia stage purpose (from User Guide)
2. Exact element type definitions (from Data Model reference)
3. Complete JSON output schema matching the Pydantic models
4. Rules: use exact Arcadia terminology, reference existing elements by ID
5. Placeholders: `{requirements}`, `{existing_elements}`

Files:
- `prompts/generate_capella_oa.txt` -- **rewrite** (currently ~60 lines, will become ~150)
- `prompts/generate_capella_sa.txt` -- **rewrite**
- `prompts/generate_capella_la.txt` -- **rewrite**
- `prompts/generate_capella_pa.txt` -- **rewrite**
- `prompts/generate_capella_epbs.txt` -- **new**

#### Instruct prompt

- `prompts/instruct_capella.txt` -- **rewrite** to cover all element types and reference correct Capella menu paths from the User Manual (section 14: Properties documents each element type's property page)

### 5. Generate Stage (`src/stages/generate.py`)

Update PROMPT_MAP:
```python
PROMPT_MAP = {
    ("capella", "operational_analysis"): "generate_capella_oa.txt",
    ("capella", "system_needs_analysis"): "generate_capella_sa.txt",
    ("capella", "system_analysis"): "generate_capella_sa.txt",  # backward compat
    ("capella", "logical_architecture"): "generate_capella_la.txt",
    ("capella", "physical_architecture"): "generate_capella_pa.txt",
    ("capella", "epbs"): "generate_capella_epbs.txt",
}
```

## What Does NOT Change

- Pipeline architecture (analyze → clarify → generate → link → instruct)
- Batch workflow and project persistence
- Frontend UI (tree view already handles arbitrary collections)
- Export (JSON/XLSX/Text already iterate layers and collections dynamically)
- Chat agent and tools (operate on element IDs, layer-agnostic)
- Rhapsody/SysML option
- LLM provider architecture
- Cost tracking
- All existing non-Capella tests
