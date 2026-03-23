import json
from unittest.mock import patch, MagicMock
from src.stages.analyze import analyze_requirements
from src.stages.clarify import apply_clarifications
from src.stages.generate import generate_layer
from src.stages.link import generate_links
from src.stages.instruct import generate_instructions
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


def test_apply_clarifications_updates_text(sample_requirements):
    clarifications = {"REQ-SAR-004": "Short durations means up to 30 minutes"}
    result = apply_clarifications(sample_requirements, clarifications)
    assert len(result) == 3
    # The clarified requirement should have the clarification appended
    req_004 = next(r for r in result if r.id == "REQ-SAR-004")
    assert "30 minutes" in req_004.text
    assert "[Clarification:" in req_004.text


def test_apply_clarifications_preserves_unclarified(sample_requirements):
    clarifications = {"REQ-SAR-004": "30 minutes max"}
    result = apply_clarifications(sample_requirements, clarifications)
    req_001 = next(r for r in result if r.id == "REQ-SAR-001")
    assert "[Clarification:" not in req_001.text


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


def test_generate_invalid_mode_raises(sample_requirements):
    tracker = CostTracker(model="test-model")
    import pytest
    with pytest.raises(ValueError, match="No prompt template"):
        generate_layer("invalid", "operational_analysis", sample_requirements, tracker)


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


def test_instruct_rhapsody_returns_steps():
    model_data = {"layers": {"block_definition": {"blocks": [{"id": "BDD-001", "name": "Test"}]}}}
    mock_response = {
        "tool": "IBM Rhapsody 10.0",
        "steps": [
            {"step": 1, "action": "Create project", "detail": "File > New > Project", "layer": "general"}
        ]
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.instruct.call_llm", return_value=mock_response):
        result = generate_instructions("rhapsody", model_data, tracker)
    assert result["tool"] == "IBM Rhapsody 10.0"


def test_generate_with_existing_elements(sample_requirements):
    existing = {
        "entities": [{"id": "OE-001", "name": "PIB Icebreaker", "type": "OperationalEntity"}],
        "capabilities": [], "scenarios": [], "activities": [],
    }
    mock_response = {
        "entities": [{"id": "OE-005", "name": "Coast Guard HQ", "type": "OperationalEntity", "actors": []}],
        "capabilities": [], "scenarios": [], "activities": [],
    }
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("capella", "operational_analysis", sample_requirements, tracker,
                                existing_elements=existing)
    assert result["entities"][0]["id"] == "OE-005"


def test_generate_without_existing_elements_still_works(sample_requirements):
    mock_response = {"entities": [{"id": "OE-001", "name": "Test", "type": "OperationalEntity", "actors": []}],
                     "capabilities": [], "scenarios": [], "activities": []}
    tracker = CostTracker(model="test-model")
    with patch("src.stages.generate.call_llm", return_value=mock_response):
        result = generate_layer("capella", "operational_analysis", sample_requirements, tracker)
    assert "entities" in result


def test_link_with_existing_links(sample_requirements):
    elements = {"operational_analysis": {"activities": [{"id": "OA-005", "name": "New Activity"}]}}
    existing_links = [{"id": "LNK-001", "source": "OA-001", "target": "REQ-001", "type": "satisfies", "description": "existing"}]
    mock_response = {"links": [{"id": "LNK-010", "source": "OA-005", "target": "REQ-SAR-007", "type": "satisfies", "description": "new"}]}
    tracker = CostTracker(model="test-model")
    with patch("src.stages.link.call_llm", return_value=mock_response):
        result = generate_links("capella", elements, sample_requirements, tracker, existing_links=existing_links)
    assert result["links"][0]["id"] == "LNK-010"
