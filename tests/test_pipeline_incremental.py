from src.pipeline import merge_batch_into_project, fix_id_collisions
from src.models import ProjectModel, ProjectMeta, Meta, Requirement, Link


def make_empty_project():
    return ProjectModel(
        project=ProjectMeta(name="Test"), batches=[],
        meta=Meta(source_file="project", mode="capella", selected_layers=[],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[], layers={}, links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )


def test_merge_appends_requirements():
    project = make_empty_project()
    merge_batch_into_project(project,
        [Requirement(id="REQ-001", text="Test", source_dig="DIG-001")],
        {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Test"}]}},
        [Link(id="LNK-001", source="OE-001", target="REQ-001", type="satisfies", description="test")],
        {"tool": "Capella 7.0", "steps": []},
        "test.xlsx", ["operational_analysis"], "test-model", 0.05)
    assert len(project.requirements) == 1
    assert "operational_analysis" in project.layers
    assert len(project.links) == 1
    assert len(project.batches) == 1
    assert project.batches[0].id == "batch-001"


def test_merge_second_batch_accumulates():
    project = make_empty_project()
    merge_batch_into_project(project,
        [Requirement(id="REQ-001", text="First", source_dig="DIG-001")],
        {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Entity A"}]}},
        [], {"tool": "Capella 7.0", "steps": []},
        "batch1.xlsx", ["operational_analysis"], "test", 0.01)
    merge_batch_into_project(project,
        [Requirement(id="REQ-002", text="Second", source_dig="DIG-002")],
        {"operational_analysis": {"entities": [{"id": "OE-002", "name": "Entity B"}]}},
        [], {"tool": "Capella 7.0", "steps": []},
        "batch2.xlsx", ["operational_analysis"], "test", 0.02)
    assert len(project.requirements) == 2
    assert len(project.layers["operational_analysis"]["entities"]) == 2
    assert len(project.batches) == 2
    assert project.batches[1].id == "batch-002"


def test_fix_id_collisions_renames_duplicates():
    existing_ids = {"OE-001", "OE-002"}
    new_elements = [{"id": "OE-001", "name": "Duplicate"}, {"id": "OE-003", "name": "New"}]
    fixed = fix_id_collisions(new_elements, existing_ids)
    ids = {e["id"] for e in fixed}
    assert "OE-001" not in ids
    assert "OE-003" in ids
    assert len(ids) == 2


def test_fix_id_collisions_no_collisions():
    existing_ids = {"OE-001"}
    new_elements = [{"id": "OE-002", "name": "New"}]
    fixed = fix_id_collisions(new_elements, existing_ids)
    assert fixed[0]["id"] == "OE-002"


def test_merge_fixes_collisions():
    project = make_empty_project()
    project.layers = {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Existing"}]}}
    merge_batch_into_project(project,
        [Requirement(id="REQ-002", text="New", source_dig="DIG-002")],
        {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Collision"}]}},
        [], {"tool": "Capella 7.0", "steps": []},
        "batch2.xlsx", ["operational_analysis"], "test", 0.01)
    entities = project.layers["operational_analysis"]["entities"]
    assert len(entities) == 2
    ids = {e["id"] for e in entities}
    assert len(ids) == 2  # No duplicates
