from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .annealing import NanoAllocationProblem, simulated_annealing
from .csp import RecoveryCSP, solve_recovery_csp
from .data_models import (CSPResult, MissionDataset, Requirements, SAResult, UCSResult)
from .requirements import derive_requirements
from .ucs import uniform_cost_search
from .validation import validate_csp, validate_integrated, validate_sa, validate_ucs


@dataclass
class Attempt:
    number: int
    power_fraction: float
    excluded_edges: List[Tuple[str, str]]
    ucs: Optional[UCSResult] = None
    sa: Optional[SAResult] = None
    req: Optional[Requirements] = None
    csp: Optional[CSPResult] = None
    outcome: str = ""
    action: str = ""


@dataclass
class MissionOutcome:
    success: bool
    attempts: List[Attempt]
    ucs: Optional[UCSResult]
    sa: Optional[SAResult]
    req: Optional[Requirements]
    csp: Optional[CSPResult]
    csp_first: Optional[CSPResult]
    csp_model: Optional[RecoveryCSP]
    bounds_log: List[str]
    makespan_search: List[dict]
    checks: List[Dict]
    health_after: Dict[str, float] = field(default_factory=dict)
    status: str = ""


def _worst_edge(ucs: UCSResult, ds: MissionDataset) -> Tuple[str, str]:
    edges = [ds.network.edge(a, b) for a, b in zip(ucs.path, ucs.path[1:])]
    e = max(edges, key=lambda e: e.loss_kW)
    return (e.u, e.v)


def minimize_makespan(req: Requirements, ds: MissionDataset, first: CSPResult,
                      node_limit: int = 200_000):
    best, log = first, []
    H = first.makespan - 1
    while H > 0:
        res, model, _ = solve_recovery_csp(req, ds.lab, horizon=H, node_limit=node_limit)
        log.append({"horizon": H, "solved": res.solved, "nodes": res.nodes,
                    "reason": res.failure_reason if not res.solved else f"makespan {res.makespan}"})
        if not res.solved:
            break
        best = res
        H = res.makespan - 1
    return best, log


def estimate_health(ds: MissionDataset, sa: SAResult) -> Dict[str, float]:
    serve = {"STR": "SR", "FLC": "FS", "STB": "FS", "SEN": "SN", "LSC": "ES"}
    cats = {c.id: c for c in ds.nano.categories}
    out = {}
    for s in ds.subsystems:
        c = cats[serve[s["id"]]]
        phi = 1 - math.exp(-sa.allocation[c.id] / c.saturation_NU)
        out[s["id"]] = round(s["health_pct"] + (100 - s["health_pct"]) * phi, 1)
    return out


def run_mission(ds: MissionDataset, seed: Optional[int] = None, verbose: bool = True) -> MissionOutcome:
    seed = ds.mission["seed"] if seed is None else seed
    rules = ds.rules
    rho = ds.nano.initial_power_fraction
    excluded: List[Tuple[str, str]] = []
    attempts: List[Attempt] = []
    say = print if verbose else (lambda *a, **k: None)

    for n in range(1, ds.mission["max_replanning_attempts"] + 1):
        att = Attempt(n, rho, list(excluded))
        attempts.append(att)
        say(f"\n=== JARVIS planning attempt {n}: rho={rho:.2f}, excluded edges={excluded or 'none'} ===")

        ucs = uniform_cost_search(ds.network, ds.reactor["available_output_kW"],
                                  ds.critical_load_kW, excluded_edges=excluded)
        att.ucs = ucs
        if not ucs.found or ucs.power_budget_kW <= 0:
            att.outcome = "UCS: no admissible route" if not ucs.found else "UCS: route budget <= 0"
            if not ucs.found:
                att.action = "ABORT: no safe route exists - manual intervention required"
                say(att.outcome, "->", att.action)
                break
            excluded.append(_worst_edge(ucs, ds))
            att.action = f"exclude edge {excluded[-1]} and re-route"
            say(att.outcome, "->", att.action)
            continue
        say(f"[UCS] route {' -> '.join(ucs.path)} cost={ucs.path_cost:.2f} "
            f"delivered={ucs.delivered_power_kW:.1f} kW budget B={ucs.power_budget_kW:.1f} kW")

        problem = NanoAllocationProblem(ds.nano, ucs.power_budget_kW, rho, ucs.total_thermal_C)
        sa = simulated_annealing(problem, ds.annealing, seed)
        att.sa = sa
        if not sa.feasible:
            att.outcome = "SA: " + sa.termination
            excluded.append(_worst_edge(ucs, ds))
            att.action = f"route too weak: exclude edge {excluded[-1]} and re-route"
            say(att.outcome, "->", att.action)
            continue
        say(f"[SA ] allocation {sa.allocation} J={sa.objective:.3f} P_nano={sa.nano_power_kW:.1f} kW "
            f"P_res={sa.residual_power_kW:.1f} kW")

        req = derive_requirements(ds, ucs, sa)
        att.req = req
        csp_res, model, bounds_log = solve_recovery_csp(req, ds.lab)
        att.csp = csp_res
        if not csp_res.solved:
            att.outcome = "CSP infeasible: " + csp_res.failure_reason
            new_rho = round(rho - rules["replan_power_fraction_step"], 4)
            if new_rho >= rules["min_power_fraction"] - 1e-9:
                att.action = (f"reduce nanomaterial power fraction rho {rho:.2f} -> {new_rho:.2f} "
                              f"to free laboratory power; re-run SA and CSP")
                rho = new_rho
            else:
                excluded.append(_worst_edge(ucs, ds))
                att.action = f"rho at minimum: exclude edge {excluded[-1]}, reset rho, re-route"
                rho = ds.nano.initial_power_fraction
            say("[CSP]", att.outcome, "->", att.action)
            continue
        say(f"[CSP] schedule found: makespan={csp_res.makespan} slots, nodes={csp_res.nodes}, "
            f"backtracks={csp_res.backtracks}")

        best, ms_log = minimize_makespan(req, ds, csp_res)
        att.outcome = "feasible"
        att.action = "validate and commit"
        checks = (validate_ucs(ds, ucs) + validate_sa(ds, ucs, sa) +
                  validate_csp(ds, req, best) + validate_integrated(ds, ucs, sa, req, best))
        success = all(c["passed"] for c in checks)
        health = estimate_health(ds, sa)
        status = ("ARMOR RESTORED - OPERATIONAL AND SAFE" if success
                  else "RECOVERY PLAN REJECTED BY VALIDATION")
        return MissionOutcome(success, attempts, ucs, sa, req, best, csp_res, model, bounds_log,
                              ms_log, checks, health, status)

    last = attempts[-1]
    status = ("RECOVERY ABORTED - no safe power route; armor held in safe mode for manual intervention"
              if last.action.startswith("ABORT") else "RECOVERY FAILED - replanning budget exhausted")
    return MissionOutcome(False, attempts, last.ucs, last.sa, last.req, last.csp, last.csp, None,
                          [], [], [], {}, status)
