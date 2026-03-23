# src/stages/generate.py
import json
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm
from src.models import Requirement

PROMPT_MAP = {
    ("capella", "operational_analysis"): "generate_capella_oa.txt",
    ("capella", "system_analysis"): "generate_capella_sa.txt",
    ("capella", "logical_architecture"): "generate_capella_la.txt",
    ("capella", "physical_architecture"): "generate_capella_pa.txt",
    ("rhapsody", "requirements_diagram"): "generate_rhapsody_req.txt",
    ("rhapsody", "block_definition"): "generate_rhapsody_bdd.txt",
    ("rhapsody", "internal_block"): "generate_rhapsody_ibd.txt",
    ("rhapsody", "activity_diagram"): "generate_rhapsody_act.txt",
    ("rhapsody", "sequence_diagram"): "generate_rhapsody_seq.txt",
    ("rhapsody", "state_machine"): "generate_rhapsody_stm.txt",
}


def generate_layer(mode: str, layer_key: str, requirements: list[Requirement], tracker: CostTracker, client=None) -> dict:
    """Stage 3: Generate model elements for a single layer/diagram type."""
    prompt_file = PROMPT_MAP.get((mode, layer_key))
    if not prompt_file:
        raise ValueError(f"No prompt template for mode={mode}, layer={layer_key}")
    template = (PROMPTS_DIR / prompt_file).read_text()
    reqs_json = json.dumps([r.model_dump() for r in requirements], indent=2)
    prompt = template.format(requirements=reqs_json)
    return call_llm(prompt=prompt, cost_tracker=tracker, call_type="generate", stage=f"generate_{layer_key}", client=client)
