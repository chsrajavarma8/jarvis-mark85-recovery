from __future__ import annotations

import math
from typing import Dict, List

from .annealing import NanoAllocationProblem
from .data_models import CSPResult, MissionDataset, Requirements, SAResult, UCSResult
from .ucs import enumerate_simple_paths


def _check(stage: str, name: str, ok: bool, detail: str) -> Dict:
    return {"stage": stage, "check": name, "passed": bool(ok), "detail": detail}


def validate_ucs(ds: MissionDataset, u: UCSResult) -> List[Dict]:
    net, out = ds.network, []
    out.append(_check("UCS", "route found", u.found, " -> ".join(u.path)))
    if not u.found:
        return out
    edges = [net.edge(a, b) for a, b in zip(u.path, u.path[1:])]
    out.append(_check("UCS", "starts at source / ends at goal",
                      u.path[0] == net.source and u.path[-1] == net.goal,
                      f"{u.path[0]} ... {u.path[-1]}"))
    failed = [p for p in u.path if net.nodes[p].failed]
    out.append(_check("UCS", "avoids FAILED components", not failed, f"failed on route: {failed or 'none'}"))
    mincap = min(e.capacity_kW for e in edges)
    out.append(_check("UCS", "capacity >= required throughput", mincap >= net.required_throughput_kW,
                      f"bottleneck {mincap:.0f} kW >= {net.required_throughput_kW:.0f} kW"))
    th = sum(e.thermal_C for e in edges)
    out.append(_check("UCS", "route thermal <= limit", th <= net.thermal_limit_C + 1e-9,
                      f"{th:.2f} C <= {net.thermal_limit_C:.2f} C"))
    cost = sum(e.cost(net.cost_weights) for e in edges)
    out.append(_check("UCS", "reported cost = recomputed cost", math.isclose(cost, u.path_cost, abs_tol=1e-6),
                      f"{cost:.4f} vs {u.path_cost:.4f}"))
    feas = [r for r in enumerate_simple_paths(net)
            if r["feasible"] and not any((a, b) in set(map(tuple, u.excluded_edges))
                                         for a, b in zip(r["path"], r["path"][1:]))]
    best = min(r["cost"] for r in feas)
    out.append(_check("UCS", "optimal vs exhaustive enumeration", math.isclose(best, u.path_cost, abs_tol=1e-6),
                      f"UCS {u.path_cost:.2f} = best of {len(feas)} feasible routes {best:.2f}"))
    out.append(_check("UCS", "delivered power covers critical load", u.power_budget_kW > 0,
                      f"delivered {u.delivered_power_kW:.1f} kW - critical {u.critical_load_kW:.0f} kW = "
                      f"budget {u.power_budget_kW:.1f} kW"))
    return out


def validate_sa(ds: MissionDataset, u: UCSResult, s: SAResult) -> List[Dict]:
    prob = NanoAllocationProblem(ds.nano, u.power_budget_kW, s.power_fraction, u.total_thermal_C)
    x, out = s.allocation, []
    for c in ds.nano.categories:
        out.append(_check("SA", f"{c.id} within [{c.min_NU}, {c.max_NU}] NU",
                          c.min_NU <= x[c.id] <= c.max_NU, f"x_{c.id} = {x[c.id]}"))
    m = prob.material(x)
    out.append(_check("SA", "material <= reserve", m <= ds.nano.reserve_NU, f"{m} <= {ds.nano.reserve_NU} NU"))
    p = prob.power(x)
    out.append(_check("SA", "nano power <= rho * B", p <= prob.power_cap + 1e-9,
                      f"{p:.1f} <= {prob.power_cap:.1f} kW (rho={s.power_fraction:.2f})"))
    th = u.total_thermal_C + prob.heat(x)
    out.append(_check("SA", "armor thermal <= limit", th <= ds.nano.armor_thermal_limit_C + 1e-9,
                      f"{th:.2f} <= {ds.nano.armor_thermal_limit_C:.1f} C"))
    J = prob.objective(x)
    out.append(_check("SA", "reported objective = recomputed", math.isclose(J, s.objective, abs_tol=1e-9),
                      f"J = {J:.4f}"))
    out.append(_check("SA", "final J >= initial J", s.objective >= s.initial_objective - 1e-9,
                      f"{s.objective:.3f} >= {s.initial_objective:.3f}"))
    return out


def validate_csp(ds: MissionDataset, req: Requirements, c: CSPResult) -> List[Dict]:
    out = [_check("CSP", "schedule found", c.solved, c.failure_reason or f"makespan {c.makespan} slots")]
    if not c.solved:
        return out
    sch = c.schedule
    tasks = {t.id: t for t in req.tasks}
    out.append(_check("CSP", "every task scheduled", set(sch) == set(tasks), f"{len(sch)}/{len(tasks)} tasks"))
    bad = [f"{p}->{k}" for k, t in tasks.items() for p in t.after if sch[k]["start"] < sch[p]["end"]]
    out.append(_check("CSP", "C1 precedence", not bad, ", ".join(bad) or "all dependencies respected"))
    bad = []
    for s in ds.lab.separations:
        gap = sch[s["second"]]["start"] - sch[s["first"]]["end"]
        if gap < s["min_gap_slots"]:
            bad.append(f"{s['first']}->{s['second']} gap {gap}")
    out.append(_check("CSP", "C2 safety separation", not bad, ", ".join(bad) or "cool-down gaps respected"))

    def overlap(a, b):
        return sch[a]["start"] < sch[b]["end"] and sch[b]["start"] < sch[a]["end"]

    bad = [f"{n['a']}|{n['b']}" for n in ds.lab.no_overlap if overlap(n["a"], n["b"])]
    out.append(_check("CSP", "C3 safety no-overlap", not bad, ", ".join(bad) or "no forbidden overlaps"))
    bad, ids = [], list(sch)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            shared = set(sch[a]["resources"].values()) & set(sch[b]["resources"].values())
            if shared and overlap(a, b):
                bad.append(f"{a}/{b} on {shared}")
    out.append(_check("CSP", "C4 resource exclusivity", not bad, ", ".join(bad) or "no unit double-booked"))
    bad = []
    units = {u.id: u for lst in ds.lab.resources.values() for u in lst}
    for k, v in sch.items():
        for rtype, uid in v["resources"].items():
            if tasks[k].needs[rtype] not in units[uid].capabilities:
                bad.append(f"{k} on {uid}")
    out.append(_check("CSP", "equipment compatibility", not bad, ", ".join(bad) or "all units capable"))
    H = req.horizon
    power = [sum(v["power_kW"] for v in sch.values() if v["start"] <= t < v["end"]) for t in range(H)]
    techs = [sum(v["technicians"] for v in sch.values() if v["start"] <= t < v["end"]) for t in range(H)]
    out.append(_check("CSP", "C5 power profile <= P_res", max(power) <= req.power_cap_kW + 1e-9,
                      f"peak {max(power):.0f} kW <= {req.power_cap_kW:.1f} kW"))
    out.append(_check("CSP", "C6 technicians", max(techs) <= req.technicians,
                      f"peak {max(techs)} <= {req.technicians}"))
    bad = [k for k, t in tasks.items() if (t.deadline is not None and sch[k]["end"] > t.deadline)
           or sch[k]["end"] > H]
    out.append(_check("CSP", "C7 deadlines / horizon", not bad, ", ".join(bad) or f"makespan {c.makespan} <= {H}"))
    durs = [k for k, t in tasks.items() if sch[k]["end"] - sch[k]["start"] != t.duration]
    out.append(_check("CSP", "durations match derived requirements", not durs, ", ".join(durs) or "ok"))
    return out


def validate_integrated(ds: MissionDataset, u: UCSResult, s: SAResult,
                        req: Requirements, c: CSPResult) -> List[Dict]:
    out = []
    peak_lab = 0.0
    if c.solved:
        peak_lab = max(sum(v["power_kW"] for v in c.schedule.values() if v["start"] <= t < v["end"])
                       for t in range(req.horizon))
    demand = u.critical_load_kW + s.nano_power_kW + peak_lab
    out.append(_check("INTEGRATED", "power balance  P_crit + P_nano + peak P_lab <= P_delivered",
                      demand <= u.delivered_power_kW + 1e-9,
                      f"{u.critical_load_kW:.0f} + {s.nano_power_kW:.1f} + {peak_lab:.0f} = {demand:.1f} "
                      f"<= {u.delivered_power_kW:.1f} kW"))
    out.append(_check("INTEGRATED", "reactor balance  P_delivered + losses <= P_avail",
                      u.delivered_power_kW + u.total_loss_kW <= ds.reactor["available_output_kW"] + 1e-9,
                      f"{u.delivered_power_kW:.0f} + {u.total_loss_kW:.0f} <= {ds.reactor['available_output_kW']} kW"))
    out.append(_check("INTEGRATED", "thermal  theta_route + theta_nano <= Theta_armor",
                      s.total_thermal_C <= ds.nano.armor_thermal_limit_C + 1e-9,
                      f"{u.total_thermal_C:.2f} + {s.nano_heat_C:.2f} = {s.total_thermal_C:.2f} "
                      f"<= {ds.nano.armor_thermal_limit_C} C"))
    sp_min = next(cat.min_NU for cat in ds.nano.categories if cat.id == "SP")
    out.append(_check("INTEGRATED", "mandatory structural protection",
                      s.allocation["SP"] >= sp_min, f"x_SP = {s.allocation['SP']} >= {sp_min} NU"))
    out.append(_check("INTEGRATED", "consumed nanomaterial is replenished",
                      c.solved and "NANO_REPL" in c.schedule,
                      f"{s.material_used_NU} NU replenished in slots "
                      f"{c.schedule['NANO_REPL']['start']}-{c.schedule['NANO_REPL']['end']}" if c.solved else "no schedule"))
    r = ds.rules
    deficit = r["armor_battery_capacity_kWh"] * (r["target_state_of_charge"] - r["armor_state_of_charge"])
    if c.solved:
        slots = c.schedule["CHARGE"]["duration"]
        energy = slots * r["charger_rating_kW"] * u.route_efficiency * ds.mission["slot_minutes"] / 60
    else:
        energy = 0.0
    out.append(_check("INTEGRATED", "armor recharged to target state of charge", energy >= deficit - 1e-9,
                      f"{energy:.1f} kWh delivered >= {deficit:.1f} kWh deficit"))
    out.append(_check("INTEGRATED", "mission completes before deadline",
                      c.solved and c.makespan <= ds.mission["horizon_slots"],
                      f"{c.makespan} slots x {ds.mission['slot_minutes']} min = "
                      f"{c.makespan * ds.mission['slot_minutes'] / 60:.1f} h <= "
                      f"{ds.mission['horizon_slots'] * ds.mission['slot_minutes'] / 60:.1f} h"))
    return out
