from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    type: str
    status: str

    @property
    def failed(self) -> bool:
        return self.status == "FAILED"


@dataclass(frozen=True)
class Edge:
    u: str
    v: str
    loss_kW: float
    thermal_C: float
    switch_ms: float
    capacity_kW: float

    def cost(self, w: Dict[str, float]) -> float:
        return (w["loss"] * self.loss_kW
                + w["thermal"] * self.thermal_C
                + w["switching"] * self.switch_ms)


@dataclass
class PowerNetwork:
    source: str
    goal: str
    required_throughput_kW: float
    thermal_limit_C: float
    cost_weights: Dict[str, float]
    nodes: Dict[str, Node]
    edges: List[Edge]
    load_edges: List[Tuple[str, str]]

    def out_edges(self, u: str) -> List[Edge]:
        return [e for e in self.edges if e.u == u]

    def edge(self, u: str, v: str) -> Edge:
        for e in self.edges:
            if e.u == u and e.v == v:
                return e
        raise KeyError(f"No edge {u}->{v}")


@dataclass(frozen=True)
class NanoCategory:
    id: str
    name: str
    min_NU: int
    max_NU: int
    power_kW_per_NU: float
    heat_C_per_NU: float
    benefit_weight: float
    saturation_NU: float
    packet_NU: int


@dataclass
class NanomaterialSpec:
    reserve_NU: int
    armor_thermal_limit_C: float
    initial_power_fraction: float
    objective_weights: Dict[str, float]
    categories: List[NanoCategory]


@dataclass
class AnnealingParams:
    initial_temperature: float
    cooling_rate: float
    min_temperature: float
    iterations_per_temperature: int
    max_iterations: int
    stall_epochs: int
    step_min_NU: int
    step_max_NU: int


@dataclass(frozen=True)
class ResourceUnit:
    id: str
    rtype: str
    capabilities: Tuple[str, ...]


@dataclass
class TaskSpec:
    id: str
    name: str
    duration_rule: str
    power_kW: float
    technicians: int
    needs: Dict[str, str]
    after: List[str]
    deadline: Optional[int]


@dataclass
class LabSpec:
    resources: Dict[str, List[ResourceUnit]]
    technicians: int
    tasks: List[TaskSpec]
    separations: List[dict]
    no_overlap: List[dict]


@dataclass
class MissionDataset:
    mission: dict
    reactor: dict
    subsystems: List[dict]
    network: PowerNetwork
    nano: NanomaterialSpec
    annealing: AnnealingParams
    rules: dict
    lab: LabSpec
    source_path: str = ""

    @property
    def critical_load_kW(self) -> float:
        return float(sum(s["critical_load_kW"] for s in self.subsystems))


def load_dataset(path: str | Path) -> MissionDataset:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    pn = raw["power_network"]
    network = PowerNetwork(
        source=pn["source"], goal=pn["goal"],
        required_throughput_kW=float(pn["required_throughput_kW"]),
        thermal_limit_C=float(pn["thermal_limit_C"]),
        cost_weights=pn["cost_weights"],
        nodes={n["id"]: Node(**n) for n in pn["nodes"]},
        edges=[Edge(**e) for e in pn["edges"]],
        load_edges=[(e["u"], e["v"]) for e in pn["load_edges"]],
    )
    nm = raw["nanomaterial"]
    nano = NanomaterialSpec(
        reserve_NU=nm["reserve_NU"],
        armor_thermal_limit_C=float(nm["armor_thermal_limit_C"]),
        initial_power_fraction=float(nm["initial_power_fraction"]),
        objective_weights=nm["objective_weights"],
        categories=[NanoCategory(**c) for c in nm["categories"]],
    )
    lab_raw = raw["laboratory"]
    resources = {
        rtype: [ResourceUnit(u["id"], rtype, tuple(u["capabilities"])) for u in units]
        for rtype, units in lab_raw["resources"].items()
    }
    lab = LabSpec(
        resources=resources,
        technicians=lab_raw["technicians"],
        tasks=[TaskSpec(**t) for t in lab_raw["tasks"]],
        separations=lab_raw["separations"],
        no_overlap=lab_raw["no_overlap"],
    )
    return MissionDataset(
        mission=raw["mission"], reactor=raw["reactor"], subsystems=raw["subsystems"],
        network=network, nano=nano, annealing=AnnealingParams(**raw["annealing"]),
        rules=raw["requirement_rules"], lab=lab, source_path=str(path),
    )


@dataclass
class UCSResult:
    found: bool
    path: List[str]
    path_cost: float
    total_loss_kW: float
    total_thermal_C: float
    total_switch_ms: float
    bottleneck_capacity_kW: float
    delivered_power_kW: float
    critical_load_kW: float
    power_budget_kW: float
    route_efficiency: float
    expansions: int
    generated: int
    trace: List[dict] = field(default_factory=list)
    pruned: List[dict] = field(default_factory=list)
    excluded_edges: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class SAResult:
    feasible: bool
    allocation: Dict[str, int]
    objective: float
    energy: float
    nano_power_kW: float
    nano_heat_C: float
    material_used_NU: int
    power_cap_kW: float
    power_fraction: float
    residual_power_kW: float
    total_thermal_C: float
    iterations: int
    accepted_worse: int
    rejected_infeasible: int
    improvements: int
    history: List[dict] = field(default_factory=list)
    initial_allocation: Dict[str, int] = field(default_factory=dict)
    initial_objective: float = 0.0
    termination: str = ""


@dataclass
class TaskRequirement:
    id: str
    name: str
    duration: int
    power_kW: float
    technicians: int
    needs: Dict[str, str]
    after: List[str]
    deadline: Optional[int]
    derivation: str


@dataclass
class Requirements:
    tasks: List[TaskRequirement]
    power_cap_kW: float
    horizon: int
    technicians: int
    notes: List[str]


@dataclass
class CSPResult:
    solved: bool
    schedule: Dict[str, dict]
    makespan: int
    nodes: int
    backtracks: int
    constraint_checks: int
    fc_prunes: int
    wipeouts: int
    trace: List[str] = field(default_factory=list)
    failure_reason: str = ""
    elapsed_s: float = 0.0


def to_jsonable(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj
