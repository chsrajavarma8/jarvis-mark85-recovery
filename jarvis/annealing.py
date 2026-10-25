from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from .data_models import AnnealingParams, NanomaterialSpec, SAResult


class NanoAllocationProblem:
    def __init__(self, spec: NanomaterialSpec, power_budget_kW: float,
                 power_fraction: float, route_thermal_C: float):
        self.spec = spec
        self.cats = spec.categories
        self.ids = [c.id for c in self.cats]
        self.B = power_budget_kW
        self.rho = power_fraction
        self.power_cap = power_fraction * power_budget_kW
        self.route_thermal = route_thermal_C
        w = spec.objective_weights
        self.lam_E, self.lam_M, self.lam_W = w["energy"], w["material"], w["packet_waste"]

    def power(self, x: Dict[str, int]) -> float:
        return sum(c.power_kW_per_NU * x[c.id] for c in self.cats)

    def heat(self, x: Dict[str, int]) -> float:
        return sum(c.heat_C_per_NU * x[c.id] for c in self.cats)

    def material(self, x: Dict[str, int]) -> int:
        return sum(x.values())

    def benefit_terms(self, x: Dict[str, int]) -> Dict[str, float]:
        return {c.id: 100.0 * c.benefit_weight * (1.0 - math.exp(-x[c.id] / c.saturation_NU))
                for c in self.cats}

    def objective(self, x: Dict[str, int]) -> float:
        benefit = sum(self.benefit_terms(x).values())
        energy_pen = self.lam_E * self.power(x) / self.B
        material_pen = self.lam_M * self.material(x) / self.spec.reserve_NU
        waste_pen = self.lam_W * sum((x[c.id] % c.packet_NU) / c.packet_NU for c in self.cats)
        return benefit - energy_pen - material_pen - waste_pen

    def violations(self, x: Dict[str, int]) -> List[str]:
        v = []
        for c in self.cats:
            if x[c.id] < c.min_NU:
                v.append(f"{c.id} below mandatory minimum ({x[c.id]} < {c.min_NU})")
            if x[c.id] > c.max_NU:
                v.append(f"{c.id} above maximum ({x[c.id]} > {c.max_NU})")
        if self.material(x) > self.spec.reserve_NU:
            v.append(f"material {self.material(x)} > reserve {self.spec.reserve_NU}")
        if self.power(x) > self.power_cap + 1e-9:
            v.append(f"power {self.power(x):.1f} > cap {self.power_cap:.1f} kW")
        total_heat = self.route_thermal + self.heat(x)
        if total_heat > self.spec.armor_thermal_limit_C + 1e-9:
            v.append(f"thermal {total_heat:.2f} > limit {self.spec.armor_thermal_limit_C} C")
        return v

    def feasible(self, x: Dict[str, int]) -> bool:
        return not self.violations(x)

    def initial_solution(self) -> Dict[str, int]:
        return {c.id: c.min_NU for c in self.cats}

    def neighbor(self, x: Dict[str, int], rng: random.Random,
                 step_min: int, step_max: int) -> Tuple[Dict[str, int], str]:
        y = dict(x)
        delta = rng.randint(step_min, step_max)
        kind = rng.choices(["transfer", "add", "remove"], weights=[0.6, 0.2, 0.2])[0]
        i = rng.choice(self.ids)
        if kind == "transfer":
            j = rng.choice([k for k in self.ids if k != i])
            y[i] -= delta
            y[j] += delta
            desc = f"move {delta} NU {i}->{j}"
        elif kind == "add":
            y[i] += delta
            desc = f"add {delta} NU to {i}"
        else:
            y[i] -= delta
            desc = f"remove {delta} NU from {i}"
        return y, desc


def simulated_annealing(problem: NanoAllocationProblem, params: AnnealingParams,
                        seed: int, greedy: bool = False,
                        max_neighbor_tries: int = 100) -> SAResult:
    rng = random.Random(seed)
    x0 = problem.initial_solution()
    if not problem.feasible(x0):
        return SAResult(feasible=False, allocation=x0, objective=float("-inf"),
                        energy=float("inf"), nano_power_kW=problem.power(x0),
                        nano_heat_C=problem.heat(x0), material_used_NU=problem.material(x0),
                        power_cap_kW=problem.power_cap, power_fraction=problem.rho,
                        residual_power_kW=problem.B - problem.power(x0),
                        total_thermal_C=problem.route_thermal + problem.heat(x0),
                        iterations=0, accepted_worse=0, rejected_infeasible=0, improvements=0,
                        initial_allocation=x0, initial_objective=problem.objective(x0),
                        termination="INFEASIBLE: mandatory minimum allocation violates "
                                    + "; ".join(problem.violations(x0)))

    cur, cur_E = dict(x0), -problem.objective(x0)
    best, best_E = dict(cur), cur_E
    T = params.initial_temperature
    history = [{"iter": 0, "T": T, "move": "initial (mandatory minimums)", "cand_J": -cur_E,
                "cur_J": -cur_E, "best_J": -best_E, "dE": 0.0, "p_accept": 1.0,
                "decision": "START", "alloc": dict(cur)}]
    it = accepted_worse = rejected = improvements = 0
    epochs_since_best = 0
    termination = ""

    while True:
        if it >= params.max_iterations:
            termination = f"max iterations ({params.max_iterations}) reached"
            break
        if not greedy and T < params.min_temperature:
            termination = f"temperature {T:.4f} < T_min {params.min_temperature}"
            break
        if epochs_since_best >= params.stall_epochs:
            termination = f"no best-improvement for {params.stall_epochs} temperature epochs"
            break

        improved_this_epoch = False
        for _ in range(params.iterations_per_temperature):
            it += 1
            cand = None
            for _try in range(max_neighbor_tries):
                y, desc = problem.neighbor(cur, rng, params.step_min_NU, params.step_max_NU)
                if problem.feasible(y):
                    cand = y
                    break
                rejected += 1
            if cand is None:
                history.append({"iter": it, "T": T, "move": "no feasible neighbour",
                                "cand_J": None, "cur_J": -cur_E, "best_J": -best_E,
                                "dE": None, "p_accept": 0.0, "decision": "STAY", "alloc": dict(cur)})
                continue
            cand_E = -problem.objective(cand)
            dE = cand_E - cur_E
            if dE <= 0:
                p, accept = 1.0, True
            elif greedy:
                p, accept = 0.0, False
            else:
                p = math.exp(-dE / T)
                accept = rng.random() < p
            if accept:
                decision = "ACCEPT-BETTER" if dE <= 0 else "ACCEPT-WORSE"
                if dE > 0:
                    accepted_worse += 1
                cur, cur_E = cand, cand_E
                if cur_E < best_E - 1e-12:
                    best, best_E = dict(cur), cur_E
                    improvements += 1
                    improved_this_epoch = True
                    decision += " (new best)"
            else:
                decision = "REJECT"
            history.append({"iter": it, "T": T, "move": desc, "cand_J": -cand_E,
                            "cur_J": -cur_E, "best_J": -best_E, "dE": dE,
                            "p_accept": p, "decision": decision, "alloc": dict(cur)})
            if it >= params.max_iterations:
                break
        epochs_since_best = 0 if improved_this_epoch else epochs_since_best + 1
        if not greedy:
            T *= params.cooling_rate

    return SAResult(
        feasible=True, allocation=best, objective=-best_E, energy=best_E,
        nano_power_kW=problem.power(best), nano_heat_C=problem.heat(best),
        material_used_NU=problem.material(best), power_cap_kW=problem.power_cap,
        power_fraction=problem.rho, residual_power_kW=problem.B - problem.power(best),
        total_thermal_C=problem.route_thermal + problem.heat(best),
        iterations=it, accepted_worse=accepted_worse, rejected_infeasible=rejected,
        improvements=improvements, history=history, initial_allocation=x0,
        initial_objective=problem.objective(x0), termination=termination)
