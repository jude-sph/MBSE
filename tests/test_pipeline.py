from src.pipeline import estimate_cost
from src.models import Requirement


def test_estimate_cost_capella():
    reqs = [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")]
    estimate = estimate_cost(
        requirements=reqs,
        mode="capella",
        selected_layers=["operational_analysis", "system_analysis"],
        model="anthropic/claude-sonnet-4",
    )
    assert "total_calls" in estimate
    assert estimate["total_calls"] == 5  # analyze(1) + generate(2) + link(1) + instruct(1)
    assert "estimated_min_cost" in estimate
    assert "estimated_max_cost" in estimate
    assert estimate["estimated_min_cost"] > 0


def test_estimate_cost_single_layer():
    reqs = [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")]
    estimate = estimate_cost(reqs, "capella", ["operational_analysis"], "anthropic/claude-sonnet-4")
    assert estimate["total_calls"] == 4  # analyze(1) + generate(1) + link(1) + instruct(1)


def test_estimate_cost_rhapsody():
    reqs = [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")]
    estimate = estimate_cost(reqs, "rhapsody", ["requirements_diagram", "block_definition", "activity_diagram"], "google/gemini-2.5-flash")
    assert estimate["total_calls"] == 6  # analyze(1) + generate(3) + link(1) + instruct(1)
    assert estimate["estimated_min_cost"] < 0.10  # Gemini Flash is very cheap
