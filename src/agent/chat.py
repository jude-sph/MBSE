# src/agent/chat.py
import json
from src.agent.tools import TOOL_DEFINITIONS, apply_tool
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm_with_tools
from src.models import MBSEModel


def _build_model_context(model: MBSEModel) -> str:
    """Build a detailed context string so the agent can reason about the model."""
    parts = []
    parts.append(f"## Current Model State")
    parts.append(f"Mode: {model.meta.mode}")

    # Requirements
    parts.append(f"\n### Requirements ({len(model.requirements)} total)")
    for req in model.requirements:
        parts.append(f"- {req.id}: {req.text[:120]}{'...' if len(req.text) > 120 else ''}")

    # Elements per layer
    for layer_key, layer_data in model.layers.items():
        if not isinstance(layer_data, dict):
            continue
        total = sum(len(v) for v in layer_data.values() if isinstance(v, list))
        parts.append(f"\n### Layer: {layer_key} ({total} elements)")
        for coll_key, elements in layer_data.items():
            if not isinstance(elements, list) or not elements:
                continue
            parts.append(f"  {coll_key}:")
            for elem in elements:
                if isinstance(elem, dict):
                    eid = elem.get("id", "?")
                    name = elem.get("name", "?")
                    parts.append(f"    - {eid}: {name}")

    # Links
    parts.append(f"\n### Links ({len(model.links)} total)")
    linked_req_ids = set()
    for link in model.links:
        parts.append(f"- {link.source} --[{link.type}]--> {link.target}")
        # Track which requirements are covered
        for req in model.requirements:
            if link.source == req.id or link.target == req.id:
                linked_req_ids.add(req.id)

    # Coverage analysis
    uncovered = [r for r in model.requirements if r.id not in linked_req_ids]
    if uncovered:
        parts.append(f"\n### Uncovered Requirements ({len(uncovered)} with no traceability links)")
        for req in uncovered:
            parts.append(f"- {req.id}: {req.text}")
    else:
        parts.append(f"\n### Coverage: 100% - all requirements have traceability links")

    return "\n".join(parts)


def chat_with_agent(
    model: MBSEModel,
    user_message: str,
    conversation_history: list[dict],
    tracker: CostTracker,
) -> tuple[str, list[dict]]:
    """Send a message to the chat agent. Returns (agent_response_text, updated_history).

    The agent may call tools to modify the model. Tool calls are executed automatically
    in a loop until the agent produces a final text response.
    """
    system_prompt = (PROMPTS_DIR / "agent_system.txt").read_text()

    # Build detailed model context so the agent can reason about the data
    model_context = _build_model_context(model)
    full_system = f"{system_prompt}\n\n{model_context}"

    # Build messages
    messages = [{"role": "system", "content": full_system}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    # Tool-calling loop
    max_iterations = 10
    for _ in range(max_iterations):
        response = call_llm_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            cost_tracker=tracker,
            call_type="chat_agent",
            stage="chat",
        )

        # Check if response has tool calls
        choice = response.choices[0]
        if choice.finish_reason == "tool_calls" or (hasattr(choice.message, 'tool_calls') and choice.message.tool_calls):
            # Execute each tool call
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = apply_tool(model, tool_call.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })
        else:
            # Final text response
            agent_text = choice.message.content or ""
            # Update history (without system message)
            updated_history = messages[1:]  # drop system prompt
            return agent_text, updated_history

    return "I've reached the maximum number of tool call iterations. Please try a simpler request.", messages[1:]
