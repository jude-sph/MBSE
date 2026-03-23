from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class CostEntry(BaseModel):
    call_type: str
    stage: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostSummary(BaseModel):
    breakdown: list[CostEntry] = Field(default_factory=list)

    @computed_field
    @property
    def total_input_tokens(self) -> int:
        return sum(e.input_tokens for e in self.breakdown)

    @computed_field
    @property
    def total_output_tokens(self) -> int:
        return sum(e.output_tokens for e in self.breakdown)

    @computed_field
    @property
    def total_cost_usd(self) -> float:
        return round(sum(e.cost_usd for e in self.breakdown), 10)

    @computed_field
    @property
    def api_calls(self) -> int:
        return len(self.breakdown)


class Requirement(BaseModel):
    id: str
    text: str
    source_dig: str


class Link(BaseModel):
    id: str
    source: str
    target: str
    type: str
    description: str


class InstructionStep(BaseModel):
    step: int
    action: str
    detail: str
    layer: str


class Meta(BaseModel):
    source_file: str
    mode: Literal["capella", "rhapsody"]
    selected_layers: list[str]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    llm_provider: str
    llm_model: str
    cost: CostSummary | None = None


class MBSEModel(BaseModel):
    meta: Meta
    requirements: list[Requirement]
    layers: dict[str, Any]
    links: list[Link]
    instructions: dict


class ProjectMeta(BaseModel):
    name: str = "Untitled Project"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BatchRecord(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_file: str
    requirement_ids: list[str]
    layers_generated: list[str]
    model: str
    cost: float


class ProjectModel(MBSEModel):
    """Extends MBSEModel with project metadata and batch history."""
    project: ProjectMeta = Field(default_factory=ProjectMeta)
    batches: list[BatchRecord] = Field(default_factory=list)
