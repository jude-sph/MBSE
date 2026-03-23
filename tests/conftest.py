import pytest
from src.models import Requirement


@pytest.fixture
def sample_requirements():
    return [
        Requirement(id="REQ-SAR-001", text="The crew shall monitor GMDSS frequencies (VHF Ch 16/70, MF 2182 kHz).", source_dig="DIG-5967"),
        Requirement(id="REQ-SAR-004", text="The vessel shall maintain station within a 10-meter radius of a fixed geographical position for short durations.", source_dig="DIG-5967"),
        Requirement(id="REQ-SAR-007", text="The vessel shall support the safe launch and recovery of the Fast Rescue Craft (FRC) from the davit.", source_dig="DIG-5967"),
    ]
