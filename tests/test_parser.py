from pathlib import Path

import pytest

from src.parser import parse_requirements_file
from src.models import Requirement

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_xlsx():
    reqs = parse_requirements_file(FIXTURES / "sample_requirements.xlsx")
    assert len(reqs) >= 1
    assert all(isinstance(r, Requirement) for r in reqs)
    assert all(r.id and r.text for r in reqs)


def test_parse_csv():
    reqs = parse_requirements_file(FIXTURES / "sample_requirements.csv")
    assert len(reqs) >= 1
    assert all(isinstance(r, Requirement) for r in reqs)


def test_parse_unknown_format_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        parse_requirements_file(Path("test.doc"))


def test_parse_xlsx_content():
    reqs = parse_requirements_file(FIXTURES / "sample_requirements.xlsx")
    assert len(reqs) == 3
    ids = [r.id for r in reqs]
    assert "REQ-SAR-001" in ids
    assert "REQ-SAR-004" in ids
    assert "REQ-SAR-007" in ids
    assert all(r.source_dig == "DIG-5967" for r in reqs)


def test_parse_csv_content():
    reqs = parse_requirements_file(FIXTURES / "sample_requirements.csv")
    assert len(reqs) == 3
    ids = [r.id for r in reqs]
    assert "REQ-SAR-001" in ids
    assert "REQ-SAR-004" in ids
    assert "REQ-SAR-007" in ids
    assert all(r.source_dig == "DIG-5967" for r in reqs)
