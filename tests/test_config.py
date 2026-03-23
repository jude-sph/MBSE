from src import config


def test_model_pricing_has_entries():
    assert len(config.MODEL_PRICING) >= 14


def test_model_catalogue_has_entries():
    assert len(config.MODEL_CATALOGUE) >= 14


def test_each_catalogue_entry_has_required_fields():
    required = {"id", "name", "provider", "price", "quality", "speed", "description", "pros", "cons"}
    for model in config.MODEL_CATALOGUE:
        missing = required - set(model.keys())
        assert not missing, f"Model {model.get('id', '?')} missing fields: {missing}"


def test_catalogue_ids_match_pricing():
    pricing_ids = set(config.MODEL_PRICING.keys())
    catalogue_ids = {m["id"] for m in config.MODEL_CATALOGUE}
    assert catalogue_ids.issubset(pricing_ids), f"Catalogue models missing from pricing: {catalogue_ids - pricing_ids}"


def test_provider_defaults():
    assert config.PROVIDER in ("anthropic", "openrouter", "local")


def test_default_mode():
    assert config.DEFAULT_MODE in ("capella", "rhapsody")


def test_package_root_is_project_root():
    assert (config.PACKAGE_ROOT / "pyproject.toml").exists()


def test_prompts_dir_exists():
    assert config.PROMPTS_DIR.exists()
