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
