from src.models import ProjectMeta, BatchRecord, ProjectModel, Meta, Requirement


def test_project_meta():
    pm = ProjectMeta(name="PIB Icebreaker")
    assert pm.name == "PIB Icebreaker"
    assert pm.created_at is not None


def test_batch_record():
    br = BatchRecord(
        id="batch-001", source_file="SAR-reqs.xlsx",
        requirement_ids=["REQ-001", "REQ-002"],
        layers_generated=["operational_analysis"],
        model="deepseek/deepseek-chat-v3-0324", cost=0.05,
    )
    assert br.id == "batch-001"
    assert len(br.requirement_ids) == 2


def test_project_model_round_trip():
    project = ProjectModel(
        project=ProjectMeta(name="Test"), batches=[],
        meta=Meta(source_file="project", mode="capella", selected_layers=[],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[], layers={}, links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )
    json_str = project.model_dump_json()
    parsed = ProjectModel.model_validate_json(json_str)
    assert parsed.project.name == "Test"


def test_project_model_has_mbse_fields():
    project = ProjectModel(
        project=ProjectMeta(name="Test"), batches=[],
        meta=Meta(source_file="project", mode="capella", selected_layers=[],
                  llm_provider="openrouter", llm_model="test"),
        requirements=[], layers={}, links=[],
        instructions={"tool": "Capella 7.0", "steps": []},
    )
    assert hasattr(project, 'meta')
    assert hasattr(project, 'layers')
    assert hasattr(project, 'links')
    assert hasattr(project, 'requirements')
