"""Agent tools for modifying MBSEModel instances in-place."""
from __future__ import annotations

from typing import Any

from src.models import MBSEModel, Link

# ---------------------------------------------------------------------------
# OpenAI-format tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "add_element",
            "description": (
                "Add a new element (entity, component, function, etc.) to a specific "
                "layer collection in the model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "layer": {
                        "type": "string",
                        "description": (
                            "The layer key, e.g. 'operational_analysis', "
                            "'system_needs_analysis', 'logical_architecture', 'physical_architecture', "
                            "'epbs', or a Rhapsody diagram key."
                        ),
                    },
                    "collection": {
                        "type": "string",
                        "description": (
                            "The collection key within the layer, e.g. 'entities', "
                            "'capabilities', 'functions', 'components'."
                        ),
                    },
                    "element": {
                        "type": "object",
                        "description": (
                            "The element dict to add. Must include an 'id' field. "
                            "Use Capella ID prefixes (OE-, OC-, SF-, LC-, PC-, etc.) "
                            "or Rhapsody prefixes (REQD-, BDD-, IBD-, etc.) as appropriate."
                        ),
                    },
                },
                "required": ["layer", "collection", "element"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_element",
            "description": (
                "Update fields on an existing element found anywhere in the model layers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "string",
                        "description": "The ID of the element to modify.",
                    },
                    "updates": {
                        "type": "object",
                        "description": "A dict of field names → new values to merge into the element.",
                    },
                },
                "required": ["element_id", "updates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_element",
            "description": (
                "Remove an element from the model by ID. Optionally cascade-deletes links "
                "that reference the removed element."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "string",
                        "description": "The ID of the element to remove.",
                    },
                    "cascade": {
                        "type": "boolean",
                        "description": (
                            "If true, also remove any links whose source or target "
                            "matches this element ID. Defaults to false."
                        ),
                        "default": False,
                    },
                },
                "required": ["element_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_link",
            "description": "Add a new traceability/relationship link between two model elements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link": {
                        "type": "object",
                        "description": (
                            "Link dict with fields: id (str), source (str), target (str), "
                            "type (str, e.g. 'satisfies', 'involves', 'refines'), "
                            "description (str)."
                        ),
                    },
                },
                "required": ["link"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_link",
            "description": "Update fields on an existing link by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link_id": {
                        "type": "string",
                        "description": "The ID of the link to modify.",
                    },
                    "updates": {
                        "type": "object",
                        "description": "A dict of field names → new values to merge into the link.",
                    },
                },
                "required": ["link_id", "updates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_link",
            "description": "Remove a traceability link from the model by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link_id": {
                        "type": "string",
                        "description": "The ID of the link to remove.",
                    },
                },
                "required": ["link_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "regenerate_layer",
            "description": (
                "Replace the entire contents of a layer with new data. Use with caution — "
                "this overwrites all elements in the specified layer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "layer": {
                        "type": "string",
                        "description": "The layer key to replace.",
                    },
                    "data": {
                        "type": "object",
                        "description": "The new layer data dict (collection key → list of elements).",
                    },
                },
                "required": ["layer", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_instruction_step",
            "description": "Append a new step to the model's instruction steps list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step": {
                        "type": "object",
                        "description": (
                            "Instruction step dict with fields: step (int), action (str), "
                            "detail (str), layer (str)."
                        ),
                    },
                },
                "required": ["step"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_elements",
            "description": (
                "List elements in a specific layer, optionally filtered by element type. "
                "Returns a read-only view — does not modify the model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "layer": {
                        "type": "string",
                        "description": "The layer key to inspect.",
                    },
                    "element_type": {
                        "type": "string",
                        "description": (
                            "Optional: filter results to elements whose 'type' field matches "
                            "this value (e.g. 'OperationalEntity')."
                        ),
                    },
                },
                "required": ["layer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_links",
            "description": (
                "List traceability links in the model, optionally filtered by element ID. "
                "Returns a read-only view — does not modify the model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "string",
                        "description": (
                            "Optional: return only links whose source or target matches "
                            "this element ID."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_element_details",
            "description": (
                "Retrieve the full dict for a specific element, searching all layers. "
                "Returns a read-only view — does not modify the model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "string",
                        "description": "The ID of the element to look up.",
                    },
                },
                "required": ["element_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_uncovered_requirements",
            "description": (
                "Get the list of requirements that have NO traceability links. "
                "Returns each uncovered requirement's ID and full text. "
                "Use this to find gaps in model coverage."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_coverage_summary",
            "description": (
                "Get a full coverage report: total requirements, covered count, "
                "uncovered count, and for each requirement whether it is covered "
                "and which links reference it. Use this for detailed traceability analysis."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ---------------------------------------------------------------------------
# Helper: iterate over all elements in the model
# ---------------------------------------------------------------------------


def _iter_elements(model: MBSEModel):
    """Yield (layer_key, collection_key, index, element_dict) for every element."""
    for layer_key, layer_value in model.layers.items():
        if not isinstance(layer_value, dict):
            continue
        for collection_key, collection in layer_value.items():
            if not isinstance(collection, list):
                continue
            for idx, element in enumerate(collection):
                if isinstance(element, dict):
                    yield layer_key, collection_key, idx, element


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _add_element(model: MBSEModel, arguments: dict) -> dict:
    layer = arguments.get("layer")
    collection = arguments.get("collection")
    element = arguments.get("element")

    if layer not in model.layers:
        return {"success": False, "message": f"Layer '{layer}' not found in model."}

    layer_data = model.layers[layer]
    if not isinstance(layer_data, dict):
        return {"success": False, "message": f"Layer '{layer}' is not a dict-based layer."}

    if collection not in layer_data:
        layer_data[collection] = []

    if not isinstance(layer_data[collection], list):
        return {
            "success": False,
            "message": f"Collection '{collection}' in layer '{layer}' is not a list.",
        }

    # Duplicate ID check
    new_id = element.get("id") if isinstance(element, dict) else None
    if new_id:
        for _, _, _, existing in _iter_elements(model):
            if existing.get("id") == new_id:
                return {
                    "success": False,
                    "message": f"An element with ID '{new_id}' already exists.",
                }

    layer_data[collection].append(element)
    return {"success": True, "message": f"Added element to {layer}/{collection}."}


def _modify_element(model: MBSEModel, arguments: dict) -> dict:
    element_id = arguments.get("element_id")
    updates = arguments.get("updates", {})

    for layer_key, collection_key, idx, element in _iter_elements(model):
        if element.get("id") == element_id:
            element.update(updates)
            model.layers[layer_key][collection_key][idx] = element
            return {
                "success": True,
                "message": f"Modified element '{element_id}' in {layer_key}/{collection_key}.",
            }

    return {"success": False, "message": f"Element '{element_id}' not found in any layer."}


def _remove_element(model: MBSEModel, arguments: dict) -> dict:
    element_id = arguments.get("element_id")
    cascade = arguments.get("cascade", False)

    found = False
    for layer_key, collection_key, idx, element in _iter_elements(model):
        if element.get("id") == element_id:
            model.layers[layer_key][collection_key].pop(idx)
            found = True
            break

    if not found:
        return {"success": False, "message": f"Element '{element_id}' not found in any layer."}

    removed_links = 0
    if cascade:
        before = len(model.links)
        model.links = [
            lnk for lnk in model.links
            if lnk.source != element_id and lnk.target != element_id
        ]
        removed_links = before - len(model.links)

    msg = f"Removed element '{element_id}'."
    if cascade:
        msg += f" Cascade-removed {removed_links} link(s)."
    return {"success": True, "message": msg}


def _add_link(model: MBSEModel, arguments: dict) -> dict:
    link_data = arguments.get("link", {})

    # Validate required fields
    for field in ("id", "source", "target", "type", "description"):
        if field not in link_data:
            return {"success": False, "message": f"Link is missing required field '{field}'."}

    # Duplicate ID check
    for existing_link in model.links:
        if existing_link.id == link_data["id"]:
            return {
                "success": False,
                "message": f"A link with ID '{link_data['id']}' already exists.",
            }

    model.links.append(
        Link(
            id=link_data["id"],
            source=link_data["source"],
            target=link_data["target"],
            type=link_data["type"],
            description=link_data["description"],
        )
    )
    return {"success": True, "message": f"Added link '{link_data['id']}'."}


def _modify_link(model: MBSEModel, arguments: dict) -> dict:
    link_id = arguments.get("link_id")
    updates = arguments.get("updates", {})

    for idx, link in enumerate(model.links):
        if link.id == link_id:
            link_dict = link.model_dump()
            link_dict.update(updates)
            model.links[idx] = Link(**link_dict)
            return {"success": True, "message": f"Modified link '{link_id}'."}

    return {"success": False, "message": f"Link '{link_id}' not found."}


def _remove_link(model: MBSEModel, arguments: dict) -> dict:
    link_id = arguments.get("link_id")
    before = len(model.links)
    model.links = [lnk for lnk in model.links if lnk.id != link_id]

    if len(model.links) == before:
        return {"success": False, "message": f"Link '{link_id}' not found."}

    return {"success": True, "message": f"Removed link '{link_id}'."}


def _regenerate_layer(model: MBSEModel, arguments: dict) -> dict:
    layer = arguments.get("layer")
    data = arguments.get("data")

    if layer not in model.layers:
        return {"success": False, "message": f"Layer '{layer}' not found in model."}

    model.layers[layer] = data
    return {"success": True, "message": f"Replaced all data in layer '{layer}'."}


def _add_instruction_step(model: MBSEModel, arguments: dict) -> dict:
    step = arguments.get("step")

    steps = model.instructions.get("steps")
    if not isinstance(steps, list):
        return {
            "success": False,
            "message": "model.instructions['steps'] is not a list.",
        }

    steps.append(step)
    return {"success": True, "message": "Appended instruction step."}


def _list_elements(model: MBSEModel, arguments: dict) -> dict:
    layer = arguments.get("layer")
    element_type = arguments.get("element_type")

    if layer not in model.layers:
        return {"success": False, "message": f"Layer '{layer}' not found in model.", "elements": []}

    layer_data = model.layers[layer]
    if not isinstance(layer_data, dict):
        return {"success": False, "message": f"Layer '{layer}' is not a dict-based layer.", "elements": []}

    elements: list[Any] = []
    for collection in layer_data.values():
        if isinstance(collection, list):
            for elem in collection:
                if isinstance(elem, dict):
                    if element_type is None or elem.get("type") == element_type:
                        elements.append(elem)

    return {"success": True, "elements": elements, "count": len(elements)}


def _list_links(model: MBSEModel, arguments: dict) -> dict:
    element_id = arguments.get("element_id")

    if element_id:
        links = [
            lnk.model_dump()
            for lnk in model.links
            if lnk.source == element_id or lnk.target == element_id
        ]
    else:
        links = [lnk.model_dump() for lnk in model.links]

    return {"success": True, "links": links, "count": len(links)}


def _get_element_details(model: MBSEModel, arguments: dict) -> dict:
    element_id = arguments.get("element_id")

    for layer_key, collection_key, _, element in _iter_elements(model):
        if element.get("id") == element_id:
            return {
                "success": True,
                "element": element,
                "layer": layer_key,
                "collection": collection_key,
            }

    return {"success": False, "message": f"Element '{element_id}' not found.", "element": None}


def _get_uncovered_requirements(model: MBSEModel, arguments: dict) -> dict:
    """Return requirements that have no traceability links."""
    linked_ids = set()
    for link in model.links:
        for req in model.requirements:
            if link.source == req.id or link.target == req.id:
                linked_ids.add(req.id)

    uncovered = [
        {"id": req.id, "text": req.text, "source_dig": req.source_dig}
        for req in model.requirements if req.id not in linked_ids
    ]
    return {
        "success": True,
        "total_requirements": len(model.requirements),
        "covered": len(linked_ids),
        "uncovered_count": len(uncovered),
        "uncovered": uncovered,
    }


def _get_coverage_summary(model: MBSEModel, arguments: dict) -> dict:
    """Return detailed per-requirement coverage with associated links."""
    req_links: dict[str, list[dict]] = {req.id: [] for req in model.requirements}
    for link in model.links:
        for req_id in req_links:
            if link.source == req_id or link.target == req_id:
                req_links[req_id].append({
                    "link_id": link.id,
                    "source": link.source,
                    "target": link.target,
                    "type": link.type,
                })

    details = []
    for req in model.requirements:
        links = req_links.get(req.id, [])
        details.append({
            "requirement_id": req.id,
            "text": req.text[:150],
            "covered": len(links) > 0,
            "link_count": len(links),
            "links": links,
        })

    covered = sum(1 for d in details if d["covered"])
    return {
        "success": True,
        "total": len(details),
        "covered": covered,
        "uncovered": len(details) - covered,
        "percentage": round(covered / len(details) * 100) if details else 100,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "add_element": _add_element,
    "modify_element": _modify_element,
    "remove_element": _remove_element,
    "add_link": _add_link,
    "modify_link": _modify_link,
    "remove_link": _remove_link,
    "regenerate_layer": _regenerate_layer,
    "add_instruction_step": _add_instruction_step,
    "list_elements": _list_elements,
    "list_links": _list_links,
    "get_element_details": _get_element_details,
    "get_uncovered_requirements": _get_uncovered_requirements,
    "get_coverage_summary": _get_coverage_summary,
}


def apply_tool(model: MBSEModel, tool_name: str, arguments: dict) -> dict:
    """Dispatch a tool call, modify the model in-place, and return a result dict.

    Returns:
        dict with at minimum {"success": bool, "message": str}.
        Read-only tools (list_elements, list_links, get_element_details) also
        include the requested data.
    """
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"success": False, "message": f"Unknown tool '{tool_name}'."}
    try:
        return handler(model, arguments)
    except Exception as exc:
        return {"success": False, "message": f"Tool '{tool_name}' raised an error: {exc}"}
