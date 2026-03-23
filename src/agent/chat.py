# src/agent/chat.py
import json
from src.agent.tools import TOOL_DEFINITIONS, apply_tool
from src.config import PROMPTS_DIR
from src.cost_tracker import CostTracker
from src.llm_client import call_llm_with_tools
from src.models import MBSEModel


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

    # Add model context to system prompt
    model_summary = json.dumps({
        "mode": model.meta.mode,
        "layers": {k: list(v.keys()) if isinstance(v, dict) else [] for k, v in model.layers.items()},
        "num_links": len(model.links),
        "num_requirements": len(model.requirements),
    })
    full_system = f"{system_prompt}\n\nCurrent model state:\n{model_summary}"

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
