from __future__ import annotations

import math
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from .annealing import NanoAllocationProblem, simulated_annealing
from .csp import solve_recovery_csp
from .data_models import MissionDataset, load_dataset, to_jsonable
from .experiments import run_experiments
from .pipeline import estimate_health, run_mission
from .requirements import derive_requirements
from .ucs import enumerate_simple_paths, uniform_cost_search
from .validation import validate_csp, validate_integrated, validate_sa, validate_ucs
from .visualization import NET_POS

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "data" / "mission_dataset.json"
MODES = ("integrated", "ucs", "sa", "csp")


class ApiError(ValueError):
    pass


def clean(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    return obj


def _num(section: dict, key: str, lo: float, hi: float, cast=float):
    if key not in section or section[key] in (None, ""):
        return None
    try:
        v = cast(section[key])
    except (TypeError, ValueError):
        raise ApiError(f"{key} must be a number")
    if not (lo <= v <= hi):
        raise ApiError(f"{key} must be between {lo:g} and {hi:g}")
    return v


def build_dataset(params: dict, path: Path = DEFAULT_DATASET) -> MissionDataset:
    ds = load_dataset(path)
    m = params.get("mission", {}) or {}
    u = params.get("ucs", {}) or {}
    s = params.get("sa", {}) or {}
    c = params.get("csp", {}) or {}

    if "failed_nodes" in m:
        failed = set(m["failed_nodes"] or [])
        for nid in failed:
            if nid not in ds.network.nodes:
                raise ApiError(f"unknown component {nid}")
            if nid in (ds.network.source, ds.network.goal):
                raise ApiError(f"{nid} cannot be failed (source / goal)")
        for nid, node in ds.network.nodes.items():
            if node.type in ("source", "load"):
                continue
            ds.network.nodes[nid] = replace(node, status="FAILED" if nid in failed
                                            else ("OK" if node.failed else node.status))
    v = _num(m, "available_kW", 100, 1500)
    if v is not None:
        ds.reactor["available_output_kW"] = v
    v = _num(m, "seed", 0, 10**9, int)
    if v is not None:
        ds.mission["seed"] = v

    for key, name in (("w_loss", "loss"), ("w_thermal", "thermal"), ("w_switching", "switching")):
        v = _num(u, key, 0, 10)
        if v is not None:
            ds.network.cost_weights = {**ds.network.cost_weights, name: v}
    v = _num(u, "thermal_limit", 1, 50)
    if v is not None:
        ds.network.thermal_limit_C = v
    v = _num(u, "required_kW", 0, 1500)
    if v is not None:
        ds.network.required_throughput_kW = v

    v = _num(s, "rho", 0.05, 1.0)
    if v is not None:
        ds.nano.initial_power_fraction = v
    for key, attr, lo, hi, cast in (("T0", "initial_temperature", 0.01, 100, float),
                                    ("alpha", "cooling_rate", 0.5, 0.999, float),
                                    ("max_iter", "max_iterations", 50, 50_000, int)):
        v = _num(s, key, lo, hi, cast)
        if v is not None:
            setattr(ds.annealing, attr, v)

    v = _num(c, "horizon", 4, 40, int)
    if v is not None:
        ds.mission["horizon_slots"] = v
    return ds


def dataset_info(path: Path = DEFAULT_DATASET) -> dict:
    ds = load_dataset(path)
    return clean({
        "mission": ds.mission, "reactor": ds.reactor, "subsystems": ds.subsystems,
        "network": _network_json(ds),
        "nano": {"reserve_NU": ds.nano.reserve_NU, "thermal_limit_C": ds.nano.armor_thermal_limit_C,
                 "rho": ds.nano.initial_power_fraction,
                 "categories": [to_jsonable(cat) for cat in ds.nano.categories]},
        "annealing": to_jsonable(ds.annealing),
        "rules": ds.rules,
        "lab": {"technicians": ds.lab.technicians,
                "tasks": [{"id": t.id, "name": t.name, "after": t.after} for t in ds.lab.tasks]},
        "defaults": {
            "mission": {"seed": ds.mission["seed"], "available_kW": ds.reactor["available_output_kW"],
                        "failed_nodes": [n.id for n in ds.network.nodes.values() if n.failed]},
            "ucs": {"w_loss": ds.network.cost_weights["loss"], "w_thermal": ds.network.cost_weights["thermal"],
                    "w_switching": ds.network.cost_weights["switching"],
                    "thermal_limit": ds.network.thermal_limit_C,
                    "required_kW": ds.network.required_throughput_kW},
            "sa": {"rho": ds.nano.initial_power_fraction, "T0": ds.annealing.initial_temperature,
                   "alpha": ds.annealing.cooling_rate, "max_iter": ds.annealing.max_iterations,
                   "budget_kW": None, "compare_hc": True},
            "csp": {"horizon": ds.mission["horizon_slots"], "mrv": True, "degree": True, "fc": True,
                    "minimize": True, "power_cap_kW": None},
        },
    })


def _network_json(ds: MissionDataset) -> dict:
    net = ds.network
    return {
        "source": net.source, "goal": net.goal,
        "required_kW": net.required_throughput_kW, "thermal_limit_C": net.thermal_limit_C,
        "weights": net.cost_weights,
        "nodes": [{"id": n.id, "label": n.label, "type": n.type, "status": n.status,
                   "x": NET_POS[n.id][0], "y": NET_POS[n.id][1]} for n in net.nodes.values()],
        "edges": [{"u": e.u, "v": e.v, "loss": e.loss_kW, "thermal": e.thermal_C, "switch": e.switch_ms,
                   "capacity": e.capacity_kW, "cost": round(e.cost(net.cost_weights), 3)} for e in net.edges],
        "load_edges": net.load_edges,
    }


def _ucs_json(ds: MissionDataset, u) -> dict:
    routes = enumerate_simple_paths(ds.network)
    return {
        "found": u.found, "path": u.path, "cost": u.path_cost, "loss_kW": u.total_loss_kW,
        "thermal_C": u.total_thermal_C, "switch_ms": u.total_switch_ms,
        "bottleneck_kW": u.bottleneck_capacity_kW, "delivered_kW": u.delivered_power_kW,
        "critical_kW": u.critical_load_kW, "budget_kW": u.power_budget_kW,
        "efficiency": u.route_efficiency, "expansions": u.expansions, "generated": u.generated,
        "pruned": len(u.pruned), "excluded_edges": u.excluded_edges, "trace": u.trace,
        "routes": routes[:40], "routes_total": len(routes),
        "routes_feasible": sum(r["feasible"] for r in routes),
        "available_kW": ds.reactor["available_output_kW"],
    }


def _downsample(history: List[dict], n: int = 700) -> List[dict]:
    if len(history) <= n:
        return history
    step = len(history) / n
    idx = sorted({int(i * step) for i in range(n)} | {len(history) - 1})
    return [history[i] for i in idx]


def _sa_json(ds: MissionDataset, s, problem: NanoAllocationProblem, hc=None) -> dict:
    cats = ds.nano.categories
    hist = [{"i": r["iter"], "T": r["T"], "cur": r["cur_J"], "best": r["best_J"], "cand": r["cand_J"],
             "d": r["decision"]} for r in s.history]
    out = {
        "feasible": s.feasible, "allocation": s.allocation, "initial": s.initial_allocation,
        "objective": s.objective, "initial_objective": s.initial_objective,
        "nano_power_kW": s.nano_power_kW, "nano_heat_C": s.nano_heat_C,
        "material_NU": s.material_used_NU, "reserve_NU": ds.nano.reserve_NU,
        "power_cap_kW": s.power_cap_kW, "rho": s.power_fraction, "budget_kW": problem.B,
        "residual_kW": s.residual_power_kW, "thermal_C": s.total_thermal_C,
        "thermal_limit_C": ds.nano.armor_thermal_limit_C, "route_thermal_C": problem.route_thermal,
        "iterations": s.iterations, "accepted_worse": s.accepted_worse,
        "rejected_infeasible": s.rejected_infeasible, "improvements": s.improvements,
        "termination": s.termination,
        "categories": [{"id": c.id, "name": c.name, "min": c.min_NU, "max": c.max_NU,
                        "power": c.power_kW_per_NU, "packet": c.packet_NU} for c in cats],
        "benefit": problem.benefit_terms(s.allocation) if s.feasible else {},
        "history": _downsample(hist),
        "first_moves": [{"i": r["iter"], "T": r["T"], "move": r["move"], "cand": r["cand_J"], "dE": r["dE"],
                         "p": r["p_accept"], "d": r["decision"]} for r in s.history[1:41]],
    }
    if hc is not None:
        out["hill_climb"] = {"objective": hc.objective, "allocation": hc.allocation,
                             "iterations": hc.iterations}
    return out


def _csp_json(ds: MissionDataset, req, first, best, model, bounds_log, ms_log) -> dict:
    H = req.horizon
    sched = best.schedule if best.solved else {}
    power = [sum(v["power_kW"] for v in sched.values() if v["start"] <= t < v["end"]) for t in range(H)]
    techs = [sum(v["technicians"] for v in sched.values() if v["start"] <= t < v["end"]) for t in range(H)]
    return {
        "solved": best.solved, "makespan": best.makespan, "first_makespan": first.makespan,
        "schedule": sched, "failure_reason": first.failure_reason,
        "nodes": first.nodes, "backtracks": first.backtracks, "checks": first.constraint_checks,
        "prunes": first.fc_prunes, "wipeouts": first.wipeouts, "elapsed_ms": round(first.elapsed_s * 1000, 2),
        "power_cap_kW": req.power_cap_kW, "horizon": H, "technicians": req.technicians,
        "slot_minutes": ds.mission["slot_minutes"],
        "tasks": [to_jsonable(t) for t in req.tasks], "notes": req.notes,
        "domains": {k: len(v) for k, v in model.domains.items()} if model else {},
        "bounds_log": bounds_log, "makespan_search": ms_log,
        "constraint_edges": model.constraint_edges() if model else [],
        "power_profile": power, "tech_profile": techs,
        "trace": first.trace[:400], "trace_total": len(first.trace),
    }


def _summary(checks: List[dict]) -> dict:
    return {"passed": sum(c["passed"] for c in checks), "total": len(checks),
            "all_passed": all(c["passed"] for c in checks) if checks else False}


def _stage_ucs(ds):
    return uniform_cost_search(ds.network, ds.reactor["available_output_kW"], ds.critical_load_kW)


def _stage_sa(ds, u, sa_params: dict):
    budget = _num(sa_params, "budget_kW", 1, 5000)
    if budget is not None:
        u = replace(u, power_budget_kW=budget)
    elif not u.found:
        raise ApiError("UCS found no admissible power route, so there is no power budget B. "
                       "Repair a component or enter a manual budget for SA.")
    elif u.power_budget_kW <= 0:
        raise ApiError(f"The UCS route delivers {u.delivered_power_kW:.0f} kW, which does not even cover the "
                       f"{u.critical_load_kW:.0f} kW critical load (B = {u.power_budget_kW:.0f} kW). "
                       "Raise the reactor output or enter a manual budget for SA.")
    problem = NanoAllocationProblem(ds.nano, u.power_budget_kW, ds.nano.initial_power_fraction,
                                    u.total_thermal_C)
    s = simulated_annealing(problem, ds.annealing, ds.mission["seed"])
    return u, problem, s


def mode_ucs(ds, p) -> dict:
    u = _stage_ucs(ds)
    checks = validate_ucs(ds, u)
    return {"ucs": _ucs_json(ds, u), "checks": checks, "summary": _summary(checks),
            "success": u.found and all(c["passed"] for c in checks),
            "status": (f"ROUTE FOUND: {' > '.join(u.path)}" if u.found
                       else "NO ADMISSIBLE ROUTE - every path violates a hard constraint")}


def mode_sa(ds, p) -> dict:
    sp = p.get("sa", {}) or {}
    u = _stage_ucs(ds)
    u2, problem, s = _stage_sa(ds, u, sp)
    hc = None
    if sp.get("compare_hc", True) and s.feasible:
        hc = simulated_annealing(problem, ds.annealing, ds.mission["seed"], greedy=True)
    checks = validate_sa(ds, u2, s) if s.feasible else [
        {"stage": "SA", "check": "feasible start", "passed": False, "detail": s.termination}]
    out = {"sa": _sa_json(ds, s, problem, hc), "checks": checks, "summary": _summary(checks),
           "success": s.feasible and all(c["passed"] for c in checks),
           "upstream": {"budget_source": "manual" if u2 is not u else "UCS route",
                        "route": u.path, "budget_kW": u2.power_budget_kW, "route_thermal_C": u2.total_thermal_C},
           "status": (f"ALLOCATION FOUND: J* = {s.objective:.3f}" if s.feasible
                      else s.termination)}
    if u.found:
        out["ucs"] = _ucs_json(ds, u)
    return out


def _solve_csp(req, ds, cp: dict):
    kw = dict(use_mrv=bool(cp.get("mrv", True)), use_degree=bool(cp.get("degree", True)),
              use_fc=bool(cp.get("fc", True)))
    first, model, bounds = solve_recovery_csp(req, ds.lab, **kw)
    best, ms_log = first, []
    if first.solved and cp.get("minimize", True):
        H = first.makespan - 1
        while H > 0:
            res, _, _ = solve_recovery_csp(req, ds.lab, horizon=H, node_limit=200_000, trace_limit=0, **kw)
            ms_log.append({"horizon": H, "solved": res.solved, "nodes": res.nodes,
                           "reason": res.failure_reason if not res.solved else f"makespan {res.makespan}"})
            if not res.solved:
                break
            best, H = res, res.makespan - 1
    return first, best, model, bounds, ms_log


def mode_csp(ds, p) -> dict:
    cp = p.get("csp", {}) or {}
    sp = p.get("sa", {}) or {}
    cap = _num(cp, "power_cap_kW", 1, 5000)
    u = _stage_ucs(ds)
    auto_rho = sp.get("rho") in (None, "") and cap is None
    rho = ds.nano.initial_power_fraction
    rho_log = []
    while True:
        ds.nano.initial_power_fraction = rho
        u2, problem, s = _stage_sa(ds, u, sp)
        if not s.feasible:
            raise ApiError("SA could not produce a feasible allocation, so CSP task durations cannot be "
                           "derived: " + s.termination)
        req = derive_requirements(ds, u2, s)
        if cap is not None:
            req = replace(req, power_cap_kW=cap,
                          notes=req.notes + [f"P_res manually overridden to {cap:.1f} kW"])
        first, best, model, bounds, ms_log = _solve_csp(req, ds, cp)
        rho_log.append({"rho": round(rho, 4), "residual_kW": s.residual_power_kW, "solved": first.solved,
                        "reason": first.failure_reason})
        nxt = round(rho - ds.rules["replan_power_fraction_step"], 4)
        if first.solved or not auto_rho or nxt < ds.rules["min_power_fraction"] - 1e-9:
            break
        rho = nxt
    checks = validate_csp(ds, req, best)
    return {"csp": _csp_json(ds, req, first, best, model, bounds, ms_log),
            "checks": checks, "summary": _summary(checks),
            "success": best.solved and all(c["passed"] for c in checks),
            "upstream": {"route": u.path, "budget_kW": u2.power_budget_kW, "allocation": s.allocation,
                         "nano_power_kW": s.nano_power_kW, "residual_kW": s.residual_power_kW,
                         "power_cap_kW": req.power_cap_kW, "rho": s.power_fraction, "rho_auto": auto_rho,
                         "rho_log": rho_log,
                         "cap_source": "manual" if cap is not None else "SA residual"},
            "status": (f"SCHEDULE FOUND: makespan {best.makespan} slots "
                       f"({best.makespan * ds.mission['slot_minutes'] / 60:.1f} h)" if best.solved
                       else "NO SCHEDULE: " + first.failure_reason)}


def mode_integrated(ds, p) -> dict:
    out = run_mission(ds, verbose=False)
    attempts = [{"number": a.number, "rho": a.power_fraction, "excluded": a.excluded_edges,
                 "outcome": a.outcome, "action": a.action,
                 "route": a.ucs.path if a.ucs and a.ucs.found else None,
                 "budget_kW": a.ucs.power_budget_kW if a.ucs and a.ucs.found else None,
                 "allocation": a.sa.allocation if a.sa and a.sa.feasible else None,
                 "objective": a.sa.objective if a.sa and a.sa.feasible else None,
                 "residual_kW": a.sa.residual_power_kW if a.sa and a.sa.feasible else None,
                 "makespan": a.csp.makespan if a.csp and a.csp.solved else None}
                for a in out.attempts]
    res: Dict[str, Any] = {"attempts": attempts, "status": out.status, "success": out.success,
                           "checks": out.checks, "summary": _summary(out.checks)}
    if out.ucs is not None:
        res["ucs"] = _ucs_json(ds, out.ucs)
    if out.sa is not None and out.ucs is not None and out.ucs.found:
        problem = NanoAllocationProblem(ds.nano, out.ucs.power_budget_kW, out.sa.power_fraction,
                                        out.ucs.total_thermal_C)
        res["sa"] = _sa_json(ds, out.sa, problem)
    if out.csp is not None and out.req is not None and out.csp_first is not None:
        res["csp"] = _csp_json(ds, out.req, out.csp_first, out.csp, out.csp_model,
                               out.bounds_log, out.makespan_search)
    if out.health_after:
        res["health"] = [{"id": s["id"], "name": s["name"], "before": s["health_pct"],
                          "after": out.health_after[s["id"]]} for s in ds.subsystems]
    if not out.checks:
        res["checks"] = [{"stage": "MISSION", "check": "recovery plan produced", "passed": False,
                          "detail": out.status}]
        res["summary"] = _summary(res["checks"])
    return res


_HANDLERS = {"integrated": mode_integrated, "ucs": mode_ucs, "sa": mode_sa, "csp": mode_csp}


def run(params: Optional[dict] = None, dataset_path: Path = DEFAULT_DATASET) -> dict:
    params = params or {}
    mode = params.get("mode", "integrated")
    t0 = time.perf_counter()
    try:
        if mode not in _HANDLERS:
            raise ApiError(f"unknown mode '{mode}' (choose one of {', '.join(MODES)})")
        ds = build_dataset(params, dataset_path)
        body = _HANDLERS[mode](ds, params)
        body.update(ok=True, error=None)
    except ApiError as e:
        body = {"ok": False, "error": str(e), "success": False, "status": "INPUT / FEASIBILITY ERROR"}
        ds = None
    body["mode"] = mode
    body["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    if ds is not None:
        body["network"] = _network_json(ds)
        body["subsystems"] = ds.subsystems
    return clean(body)


_PERF_CACHE: Dict[str, dict] = {}


def performance(dataset_path: Path = DEFAULT_DATASET) -> dict:
    if "v" in _PERF_CACHE:
        return _PERF_CACHE["v"]
    ds = load_dataset(dataset_path)
    t0 = time.perf_counter()
    out = run_mission(ds, verbose=False)
    mission_ms = (time.perf_counter() - t0) * 1000
    perf = run_experiments(ds, out)
    u, s, c = out.ucs, out.sa, out.csp
    for r in perf["route_methods"]:
        r["method"] = r["method"].replace(chr(10), " ")
    body = {
        "mission_ms": round(mission_ms, 1),
        "status": out.status, "success": out.success,
        "attempts": [{"number": a.number, "rho": a.power_fraction, "outcome": a.outcome, "action": a.action}
                     for a in out.attempts],
        "checks_passed": sum(ch["passed"] for ch in out.checks), "checks_total": len(out.checks),
        "ucs": {"path": u.path, "cost": u.path_cost, "loss_kW": u.total_loss_kW, "thermal_C": u.total_thermal_C,
                "switch_ms": u.total_switch_ms, "delivered_kW": u.delivered_power_kW, "budget_kW": u.power_budget_kW,
                "efficiency": u.route_efficiency, "expansions": u.expansions, "generated": u.generated,
                "pruned": len(u.pruned)},
        "sa": {"allocation": s.allocation, "objective": s.objective, "initial_objective": s.initial_objective,
               "material_NU": s.material_used_NU, "nano_power_kW": s.nano_power_kW, "power_cap_kW": s.power_cap_kW,
               "residual_kW": s.residual_power_kW, "thermal_C": s.total_thermal_C, "iterations": s.iterations,
               "accepted_worse": s.accepted_worse, "rejected": s.rejected_infeasible, "improvements": s.improvements,
               "rho": s.power_fraction},
        "csp": {"makespan": c.makespan, "slot_minutes": ds.mission["slot_minutes"], "horizon": ds.mission["horizon_slots"],
                "nodes": out.csp_first.nodes, "backtracks": out.csp_first.backtracks,
                "checks": out.csp_first.constraint_checks, "prunes": out.csp_first.fc_prunes,
                "makespan_search": out.makespan_search},
        "performance": {k: v for k, v in perf.items()},
    }
    _PERF_CACHE["v"] = clean(body)
    return _PERF_CACHE["v"]
