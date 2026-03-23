import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.config import MODEL_PRICING
from src.cost_tracker import CostTracker
from src.llm_client import call_llm, create_client
from src.models import MBSEModel, Meta, Requirement, Link
from src.stages.analyze import analyze_requirements
from src.stages.clarify import apply_clarifications
from src.stages.generate import generate_layer
from src.stages.link import generate_links
from src.stages.instruct import generate_instructions

logger = logging.getLogger(__name__)

STAGE_RETRIES = 2  # Total attempts per stage (1 original + 1 retry)
STAGE_RETRY_DELAY = 3  # Seconds between retries


def _run_with_retry(fn, stage_name, emit):
    """Run a stage function with retry logic. Returns the result or raises."""
    for attempt in range(1, STAGE_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt < STAGE_RETRIES:
                logger.warning(f"Stage '{stage_name}' failed (attempt {attempt}): {exc}. Retrying in {STAGE_RETRY_DELAY}s...")
                emit({"stage": stage_name, "status": "running", "detail": f"Retrying after error (attempt {attempt + 1})..."})
                time.sleep(STAGE_RETRY_DELAY)
            else:
                raise


def estimate_cost(requirements: list[Requirement], mode: str, selected_layers: list[str], model: str) -> dict:
    """Pre-run cost estimation. Returns dict with call breakdown and cost range."""
    pricing = MODEL_PRICING.get(model, {})
    input_rate = pricing.get("input_per_mtok", 0.0)
    output_rate = pricing.get("output_per_mtok", 0.0)

    num_reqs = len(requirements)
    num_layers = len(selected_layers)

    # Estimate token counts per stage
    # analyze: prompt ~500 + reqs ~100/each, output ~500
    analyze_in = 500 + num_reqs * 100
    analyze_out = 500

    # generate: prompt ~1500 + reqs ~100/each, output ~1000-2000 per layer
    gen_in = 1500 + num_reqs * 100
    gen_out_min = 800
    gen_out_max = 2000

    # link: prompt ~500 + all elements ~200/layer + reqs, output ~500-1500
    link_in = 500 + num_layers * 200 + num_reqs * 100
    link_out_min = 500
    link_out_max = 1500

    # instruct: prompt ~500 + model ~200/layer, output ~500-2000
    instruct_in = 500 + num_layers * 200
    instruct_out_min = 500
    instruct_out_max = 2000

    total_calls = 1 + num_layers + 1 + 1  # analyze + generate(N) + link + instruct

    min_tokens_in = analyze_in + gen_in * num_layers + link_in + instruct_in
    max_tokens_in = min_tokens_in  # input is deterministic
    min_tokens_out = analyze_out + gen_out_min * num_layers + link_out_min + instruct_out_min
    max_tokens_out = analyze_out + gen_out_max * num_layers + link_out_max + instruct_out_max

    min_cost = (min_tokens_in * input_rate + min_tokens_out * output_rate) / 1_000_000
    max_cost = (max_tokens_in * input_rate + max_tokens_out * output_rate) / 1_000_000

    return {
        "total_calls": total_calls,
        "num_requirements": num_reqs,
        "num_layers": num_layers,
        "model": model,
        "estimated_min_cost": round(min_cost, 4),
        "estimated_max_cost": round(max_cost, 4),
        "clarify_note": "Clarification stage may add 1 additional call if ambiguities are detected",
        "breakdown": [
            {"stage": "analyze", "calls": 1},
            {"stage": "generate", "calls": num_layers},
            {"stage": "link", "calls": 1},
            {"stage": "instruct", "calls": 1},
        ]
    }


def run_pipeline(
    requirements: list[Requirement],
    mode: str,
    selected_layers: list[str],
    model: str,
    provider: str,
    clarifications: dict[str, str] | None = None,
    emit: Callable[[dict], None] | None = None,
    cost_log_path: Path | None = None,
) -> MBSEModel:
    """Run the full 5-stage pipeline. Returns an MBSEModel.

    emit: callback for SSE events, called with {"stage": ..., "status": ..., "detail": ...}
    """
    tracker = CostTracker(model=model, cost_log_path=cost_log_path)
    client = create_client()
    _emit = emit or (lambda e: None)

    # Stage 1: Analyze
    _emit({"stage": "analyze", "status": "running", "detail": "Analyzing requirements..."})
    analysis = _run_with_retry(
        lambda: analyze_requirements(requirements, tracker, client=client),
        "analyze", _emit,
    )
    flagged_count = len(analysis.get("flagged", []))
    _emit({"stage": "analyze", "status": "complete", "detail": f"{flagged_count} issues found", "data": analysis})

    # Stage 2: Clarify (conditional)
    if clarifications:
        _emit({"stage": "clarify", "status": "running", "detail": "Applying clarifications..."})
        requirements = apply_clarifications(requirements, clarifications)
        _emit({"stage": "clarify", "status": "complete", "detail": f"{len(clarifications)} clarifications applied"})

    # Stage 3: Generate (layer by layer)
    layers = {}
    for i, layer_key in enumerate(selected_layers, 1):
        _emit({"stage": "generate", "status": "running", "detail": f"Generating {layer_key} ({i}/{len(selected_layers)})...", "cost": tracker.format_cost_line()})
        layers[layer_key] = _run_with_retry(
            lambda lk=layer_key: generate_layer(mode, lk, requirements, tracker, client=client),
            "generate", _emit,
        )
        _emit({"stage": "generate", "status": "layer_complete", "detail": f"{layer_key} complete", "cost": tracker.format_cost_line()})

    _emit({"stage": "generate", "status": "complete", "detail": f"All {len(selected_layers)} layers generated"})

    # Stage 4: Link
    _emit({"stage": "link", "status": "running", "detail": "Generating cross-element links...", "cost": tracker.format_cost_line()})
    link_result = _run_with_retry(
        lambda: generate_links(mode, layers, requirements, tracker, client=client),
        "link", _emit,
    )
    links = [Link(**l) for l in link_result.get("links", [])]
    _emit({"stage": "link", "status": "complete", "detail": f"{len(links)} links created", "cost": tracker.format_cost_line()})

    # Stage 5: Instruct
    _emit({"stage": "instruct", "status": "running", "detail": "Generating recreation instructions...", "cost": tracker.format_cost_line()})
    instructions = _run_with_retry(
        lambda: generate_instructions(mode, {"layers": layers}, tracker, client=client, emit=_emit),
        "instruct", _emit,
    )
    _emit({"stage": "instruct", "status": "complete", "detail": "Instructions generated", "cost": tracker.format_cost_line()})

    # Build final model
    model_obj = MBSEModel(
        meta=Meta(
            source_file="uploaded",
            mode=mode,
            selected_layers=selected_layers,
            llm_provider=provider,
            llm_model=model,
            cost=tracker.get_summary(),
        ),
        requirements=requirements,
        layers=layers,
        links=links,
        instructions=instructions,
    )

    # Log cost
    tracker.flush_log(run_type="pipeline_run", source_file=model_obj.meta.source_file, mode=mode, layers=selected_layers)

    _emit({"stage": "done", "status": "complete", "detail": tracker.format_cost_line()})
    return model_obj
