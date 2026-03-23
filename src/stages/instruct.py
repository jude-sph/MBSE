# src/stages/instruct.py
import json
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm


def generate_instructions(mode: str, model_data: dict, tracker: CostTracker, client=None) -> dict:
    """Stage 5: Generate tool-specific recreation instructions. Returns {tool: ..., steps: [...]}."""
    prompt_file = "instruct_capella.txt" if mode == "capella" else "instruct_rhapsody.txt"
    template = (PROMPTS_DIR / prompt_file).read_text()
    model_json = json.dumps(model_data, indent=2)
    prompt = template.format(model=model_json)
    return call_llm(prompt=prompt, cost_tracker=tracker, call_type="instruct", stage="instruct", max_tokens=8192, client=client)
