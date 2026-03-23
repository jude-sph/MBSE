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
