from __future__ import annotations

from pydantic import BaseModel, Field


# ── Operational Analysis (OA) ──────────────────────────────────────────────


class OperationalEntity(BaseModel):
    id: str
    name: str
    type: str = "OperationalEntity"
    actors: list[str] = Field(default_factory=list)


class OperationalCapability(BaseModel):
    id: str
    name: str
    involved_entities: list[str] = Field(default_factory=list)


class ScenarioStep(BaseModel):
    from_entity: str
    to_entity: str
    message: str
    sequence: int


class Scenario(BaseModel):
    id: str
    name: str
    steps: list[ScenarioStep] = Field(default_factory=list)


class OperationalActivity(BaseModel):
    id: str
    name: str
    entity: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class OperationalAnalysisLayer(BaseModel):
    entities: list[OperationalEntity] = Field(default_factory=list)
    capabilities: list[OperationalCapability] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    activities: list[OperationalActivity] = Field(default_factory=list)


# ── System Analysis (SA) ───────────────────────────────────────────────────


class SystemFunction(BaseModel):
    id: str
    name: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class SystemFunctionalExchange(BaseModel):
    id: str
    name: str
    source: str
    target: str


class SystemAnalysisLayer(BaseModel):
    functions: list[SystemFunction] = Field(default_factory=list)
    exchanges: list[SystemFunctionalExchange] = Field(default_factory=list)


# ── Logical Architecture (LA) ──────────────────────────────────────────────


class LogicalComponent(BaseModel):
    id: str
    name: str
    functions: list[str] = Field(default_factory=list)


class LogicalFunction(BaseModel):
    id: str
    name: str
    component: str


class LogicalArchitectureLayer(BaseModel):
    components: list[LogicalComponent] = Field(default_factory=list)
    functions: list[LogicalFunction] = Field(default_factory=list)


# ── Physical Architecture (PA) ─────────────────────────────────────────────


class PhysicalComponent(BaseModel):
    id: str
    name: str
    type: str
    logical_components: list[str] = Field(default_factory=list)


class PhysicalFunction(BaseModel):
    id: str
    name: str
    physical_component: str


class PhysicalLink(BaseModel):
    id: str
    name: str
    source: str
    target: str


class PhysicalArchitectureLayer(BaseModel):
    components: list[PhysicalComponent] = Field(default_factory=list)
    functions: list[PhysicalFunction] = Field(default_factory=list)
    links: list[PhysicalLink] = Field(default_factory=list)
