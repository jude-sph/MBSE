from src.agent.tools import apply_tool, TOOL_DEFINITIONS
from src.models import MBSEModel, Meta, Requirement, Link


def make_test_model():
    return MBSEModel(
        meta=Meta(source_file="test.xlsx", mode="capella", selected_layers=["operational_analysis"],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[Requirement(id="REQ-001", text="Test", source_dig="DIG-001")],
        layers={"operational_analysis": {"entities": [{"id": "OE-001", "name": "Test Entity", "type": "OperationalEntity", "actors": []}]}},
        links=[Link(id="LNK-001", source="OE-001", target="REQ-001", type="satisfies", description="test")],
        instructions={"tool": "Capella 7.0", "steps": []},
    )


def test_add_element():
    model = make_test_model()
    result = apply_tool(model, "add_element", {
        "layer": "operational_analysis",
        "collection": "entities",
        "element": {"id": "OE-002", "name": "New Entity", "type": "OperationalEntity", "actors": []}
    })
    assert result["success"]
    entities = model.layers["operational_analysis"]["entities"]
    assert len(entities) == 2
    assert entities[1]["id"] == "OE-002"


def test_modify_element():
    model = make_test_model()
    result = apply_tool(model, "modify_element", {"element_id": "OE-001", "updates": {"name": "Renamed Entity"}})
    assert result["success"]
    assert model.layers["operational_analysis"]["entities"][0]["name"] == "Renamed Entity"


def test_remove_element_cascades_links():
    model = make_test_model()
    result = apply_tool(model, "remove_element", {"element_id": "OE-001", "cascade": True})
    assert result["success"]
    assert len(model.layers["operational_analysis"]["entities"]) == 0
    assert len(model.links) == 0  # Link was cascaded


def test_add_link():
    model = make_test_model()
    result = apply_tool(model, "add_link", {
        "link": {"id": "LNK-002", "source": "OE-001", "target": "REQ-001", "type": "involves", "description": "new link"}
    })
    assert result["success"]
    assert len(model.links) == 2


def test_remove_link():
    model = make_test_model()
    result = apply_tool(model, "remove_link", {"link_id": "LNK-001"})
    assert result["success"]
    assert len(model.links) == 0


def test_list_elements():
    model = make_test_model()
    result = apply_tool(model, "list_elements", {"layer": "operational_analysis"})
    assert result["success"]
    assert len(result["elements"]) == 1


def test_tool_definitions_are_valid_openai_format():
    for tool in TOOL_DEFINITIONS:
        assert "type" in tool and tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "parameters" in tool["function"]
