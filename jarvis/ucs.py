from __future__ import annotations

import heapq
import itertools
from typing import Iterable, List, Optional, Set, Tuple

from .data_models import PowerNetwork, UCSResult


def _dominated(labels: List[Tuple[float, float]], g: float, theta: float) -> bool:
    return any(g2 <= g + 1e-9 and t2 <= theta + 1e-9 for g2, t2 in labels)


def uniform_cost_search(net: PowerNetwork,
                        available_kW: float,
                        critical_load_kW: float,
                        excluded_edges: Iterable[Tuple[str, str]] = (),
                        enforce_thermal: bool = True,
                        enforce_capacity: bool = True,
                        record_trace: bool = True) -> UCSResult:
    w = net.cost_weights
    excluded: Set[Tuple[str, str]] = set(excluded_edges)
    tie = itertools.count()
    frontier = [(0.0, next(tie), net.source, (net.source,), 0.0, 0.0, 0.0, float("inf"))]
    expanded = {}
    trace, pruned = [], []
    expansions = generated = 0

    while frontier:
        g, _, node, path, theta, loss, sw, bott = heapq.heappop(frontier)
        if _dominated(expanded.get(node, []), g, theta):
            if record_trace:
                pruned.append({"node": node, "g": round(g, 2), "theta": theta,
                               "reason": "dominated label (already expanded cheaper & cooler)"})
            continue
        expanded.setdefault(node, []).append((g, theta))
        expansions += 1

        step = {"step": expansions, "expand": node, "g": round(g, 2), "theta": round(theta, 2),
                "path": list(path), "pushed": [], "rejected": []}

        if node == net.goal:
            if record_trace:
                step["frontier_after"] = _snapshot(frontier)
                step["goal"] = True
                trace.append(step)
            delivered = min(available_kW - loss, bott)
            return UCSResult(
                found=True, path=list(path), path_cost=round(g, 4),
                total_loss_kW=loss, total_thermal_C=round(theta, 4), total_switch_ms=sw,
                bottleneck_capacity_kW=bott, delivered_power_kW=delivered,
                critical_load_kW=critical_load_kW,
                power_budget_kW=delivered - critical_load_kW,
                route_efficiency=delivered / available_kW,
                expansions=expansions, generated=generated,
                trace=trace, pruned=pruned, excluded_edges=sorted(excluded))

        for e in net.out_edges(node):
            reason = None
            if (e.u, e.v) in excluded:
                reason = "edge excluded by replanning"
            elif net.nodes[e.v].failed:
                reason = f"{e.v} FAILED (FRIDAY fault)"
            elif e.v in path:
                reason = "cycle"
            elif enforce_capacity and e.capacity_kW < net.required_throughput_kW:
                reason = f"capacity {e.capacity_kW:.0f} < required {net.required_throughput_kW:.0f} kW"
            new_theta = theta + e.thermal_C
            if reason is None and enforce_thermal and new_theta > net.thermal_limit_C + 1e-9:
                reason = f"thermal {new_theta:.1f} > limit {net.thermal_limit_C:.1f} C"
            new_g = g + e.cost(w)
            if reason is None and _dominated(expanded.get(e.v, []), new_g, new_theta):
                reason = "dominated by expanded label"
            if reason:
                step["rejected"].append({"to": e.v, "reason": reason})
                continue
            generated += 1
            heapq.heappush(frontier, (new_g, next(tie), e.v, path + (e.v,), new_theta,
                                      loss + e.loss_kW, sw + e.switch_ms,
                                      min(bott, e.capacity_kW)))
            step["pushed"].append({"to": e.v, "edge_cost": round(e.cost(w), 2),
                                   "g": round(new_g, 2), "theta": round(new_theta, 2)})
        if record_trace:
            step["frontier_after"] = _snapshot(frontier)
            trace.append(step)

    return UCSResult(found=False, path=[], path_cost=float("inf"), total_loss_kW=0,
                     total_thermal_C=0, total_switch_ms=0, bottleneck_capacity_kW=0,
                     delivered_power_kW=0, critical_load_kW=critical_load_kW,
                     power_budget_kW=-critical_load_kW, route_efficiency=0,
                     expansions=expansions, generated=generated, trace=trace,
                     pruned=pruned, excluded_edges=sorted(excluded))


def _snapshot(frontier) -> List[dict]:
    return [{"node": item[2], "g": round(item[0], 2), "theta": round(item[4], 2)}
            for item in sorted(frontier)]


def enumerate_simple_paths(net: PowerNetwork) -> List[dict]:
    w = net.cost_weights
    out = []

    def dfs(node, path, edges):
        if node == net.goal:
            out.append({
                "path": list(path),
                "cost": round(sum(e.cost(w) for e in edges), 4),
                "loss": sum(e.loss_kW for e in edges),
                "thermal": sum(e.thermal_C for e in edges),
                "bottleneck": min(e.capacity_kW for e in edges),
                "uses_failed": any(net.nodes[p].failed for p in path),
            })
            return
        for e in net.out_edges(node):
            if e.v not in path:
                dfs(e.v, path + [e.v], edges + [e])

    dfs(net.source, [net.source], [])
    for r in out:
        r["feasible"] = (not r["uses_failed"]
                         and r["bottleneck"] >= net.required_throughput_kW
                         and r["thermal"] <= net.thermal_limit_C + 1e-9)
    return sorted(out, key=lambda r: r["cost"])
