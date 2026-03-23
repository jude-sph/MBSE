import json
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm
from src.models import Requirement


def analyze_requirements(requirements: list[Requirement], tracker: CostTracker, client=None) -> dict:
    """Stage 1: Analyze requirements for ambiguity. Returns {flagged: [...], clear: [...]}."""
    template = (PROMPTS_DIR / "analyze.txt").read_text()
    reqs_json = json.dumps([r.model_dump() for r in requirements], indent=2)
    prompt = template.format(requirements=reqs_json)
    return call_llm(prompt=prompt, cost_tracker=tracker, call_type="analyze", stage="analyze", client=client)
