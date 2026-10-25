from __future__ import annotations

import statistics
import time
from collections import deque

from .annealing import NanoAllocationProblem, simulated_annealing
from .csp import solve_recovery_csp
from .ucs import uniform_cost_search


def _bfs_route(net):
    q = deque([[net.source]])
    seen = {net.source}
    while q:
        p = q.popleft()
        if p[-1] == net.goal:
            return p
        for e in net.out_edges(p[-1]):
            if e.v in seen or net.nodes[e.v].failed or e.capacity_kW < net.required_throughput_kW:
                continue
            seen.add(e.v)
            q.append(p + [e.v])
    return None


def _route_stats(net, path):
    edges = [net.edge(a, b) for a, b in zip(path, path[1:])]
    th = sum(e.thermal_C for e in edges)
    feasible = (not any(net.nodes[n].failed for n in path)
                and min(e.capacity_kW for e in edges) >= net.required_throughput_kW
                and th <= net.thermal_limit_C + 1e-9)
    return {"path": path, "cost": round(sum(e.cost(net.cost_weights) for e in edges), 2),
            "thermal": th, "feasible": feasible}


def run_experiments(ds, outcome, n_seeds: int = 30) -> dict:
    u, s = outcome.ucs, outcome.sa
    net = ds.network
    P, crit = ds.reactor["available_output_kW"], ds.critical_load_kW

    prob = NanoAllocationProblem(ds.nano, u.power_budget_kW, s.power_fraction, u.total_thermal_C)
    sa_vals, hc_vals, sa_iters, sa_times = [], [], [], []
    for seed in range(n_seeds):
        t0 = time.perf_counter()
        r = simulated_annealing(prob, ds.annealing, seed)
        sa_times.append(time.perf_counter() - t0)
        sa_vals.append(round(r.objective, 4)); sa_iters.append(r.iterations)
        hc_vals.append(round(simulated_annealing(prob, ds.annealing, seed, greedy=True).objective, 4))
    sa_summary = {
        "sa": sa_vals, "hc": hc_vals,
        "sa_mean": statistics.mean(sa_vals), "sa_std": statistics.pstdev(sa_vals),
        "sa_best": max(sa_vals), "sa_worst": min(sa_vals),
        "hc_mean": statistics.mean(hc_vals), "hc_std": statistics.pstdev(hc_vals),
        "hc_best": max(hc_vals), "hc_worst": min(hc_vals),
        "sa_wins": sum(a > b + 1e-9 for a, b in zip(sa_vals, hc_vals)),
        "sa_mean_iters": statistics.mean(sa_iters), "sa_mean_time_s": statistics.mean(sa_times),
    }

    variants = [("MRV + degree + FC", True, True, True), ("MRV + FC", True, False, True),
                ("FC only (static order)", False, False, True), ("MRV + degree, no FC", True, True, False),
                ("Plain backtracking", False, False, False)]
    csp_rows = []
    for name, mrv, deg, fc in variants:
        t0 = time.perf_counter()
        res, _, _ = solve_recovery_csp(outcome.req, ds.lab, use_mrv=mrv, use_degree=deg, use_fc=fc,
                                       node_limit=2_000_000, trace_limit=0)
        csp_rows.append({"variant": name, "solved": res.solved, "makespan": res.makespan,
                         "nodes": res.nodes, "backtracks": res.backtracks,
                         "checks": res.constraint_checks, "wipeouts": res.wipeouts,
                         "time_ms": round((time.perf_counter() - t0) * 1000, 2)})

    routes = []
    routes.append({"method": "UCS\n(all constraints)", **_route_stats(net, u.path)})
    r = uniform_cost_search(net, P, crit, enforce_thermal=False, record_trace=False)
    routes.append({"method": "UCS\nthermal-blind", **_route_stats(net, r.path)})
    r = uniform_cost_search(net, P, crit, enforce_thermal=False, enforce_capacity=False, record_trace=False)
    routes.append({"method": "UCS thermal- &\ncapacity-blind", **_route_stats(net, r.path)})
    bfs = _bfs_route(net)
    routes.append({"method": "BFS\n(fewest hops)", **_route_stats(net, bfs)})

    reps = 50
    t0 = time.perf_counter()
    for _ in range(reps):
        uniform_cost_search(net, P, crit, record_trace=False)
    ucs_ms = (time.perf_counter() - t0) / reps * 1000
    return {"sa_vs_hc": sa_summary, "csp_variants": csp_rows, "route_methods": routes,
            "timing_ms": {"ucs": round(ucs_ms, 3), "sa": round(sa_summary["sa_mean_time_s"] * 1000, 1),
                          "csp": csp_rows[0]["time_ms"]}}
