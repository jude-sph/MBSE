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


def test_operational_process():
    from src.models.capella import OperationalProcess
    p = OperationalProcess(id="OP-001", name="SAR Process", capability_ref="OC-001", activity_refs=["OA-001"])
    assert p.capability_ref == "OC-001"


def test_communication_mean():
    from src.models.capella import CommunicationMean
    cm = CommunicationMean(id="CM-001", name="VHF Radio Link", source_entity="OE-001", target_entity="OE-002")
    assert cm.source_entity == "OE-001"


def test_operational_mode_state():
    from src.models.capella import OperationalModeState
    ms = OperationalModeState(id="OMS-001", name="Standby", type="State", transitions=[{"target": "OMS-002", "trigger": "Alert"}])
    assert ms.type == "State"


def test_system_definition():
    from src.models.capella import SystemDefinition
    s = SystemDefinition(id="SYS-001", name="PIB Icebreaker", description="Coast Guard Icebreaker")
    assert s.name == "PIB Icebreaker"


def test_specified_capability():
    from src.models.capella import SpecifiedCapability
    sc = SpecifiedCapability(id="SC-001", name="Station Keeping", involved_functions=["SF-001"], involved_chains=["SFC-001"])
    assert len(sc.involved_functions) == 1


def test_logical_functional_chain():
    from src.models.capella import LogicalFunctionalChain
    lfc = LogicalFunctionalChain(id="LFC-001", name="Propulsion Chain", function_refs=["LF-001"], exchange_refs=["LFE-001"])
    assert len(lfc.function_refs) == 1


def test_hosting_component():
    from src.models.capella import HostingComponent
    hc = HostingComponent(id="HC-001", name="Bridge Console", hosted_components=["PC-001", "PC-002"])
    assert len(hc.hosted_components) == 2


def test_configuration_item():
    from src.models.capella import ConfigurationItem
    ci = ConfigurationItem(id="CI-001", name="Propulsion Control Unit", type="HW", description="Main controller", physical_component_refs=["PC-001"])
    assert ci.type == "HW"


def test_pbs_node():
    from src.models.capella import PBSNode
    node = PBSNode(id="PBS-001", name="Propulsion System", parent_id=None, children_ids=["PBS-002"], ci_ref="CI-001")
    assert node.ci_ref == "CI-001"
