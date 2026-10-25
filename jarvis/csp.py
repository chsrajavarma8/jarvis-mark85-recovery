from __future__ import annotations

import itertools
import time
from typing import Dict, List, Optional, Tuple

from .data_models import CSPResult, LabSpec, Requirements, TaskRequirement

Value = Tuple[int, Tuple[str, ...]]


class RecoveryCSP:
    def __init__(self, req: Requirements, lab: LabSpec, horizon: Optional[int] = None):
        self.req = req
        self.lab = lab
        self.H = horizon if horizon is not None else req.horizon
        self.tasks: Dict[str, TaskRequirement] = {t.id: t for t in req.tasks}
        self.order = [t.id for t in req.tasks]
        self.cap = req.power_cap_kW
        self.ntech = req.technicians
        self.prec: Dict[Tuple[str, str], int] = {}
        for t in req.tasks:
            for p in t.after:
                self.prec[(p, t.id)] = 0
        for s in lab.separations:
            self.prec[(s["first"], s["second"])] = max(self.prec.get((s["first"], s["second"]), 0),
                                                       s["min_gap_slots"])
        self.no_overlap = {frozenset((n["a"], n["b"])) for n in lab.no_overlap}
        self.domains: Dict[str, List[Value]] = {k: self._unary_domain(self.tasks[k]) for k in self.order}
        self.neighbors = self._build_neighbors()

    def compatible_units(self, task: TaskRequirement) -> Dict[str, List[str]]:
        out = {}
        for rtype, cap in task.needs.items():
            out[rtype] = [u.id for u in self.lab.resources[rtype] if cap in u.capabilities]
        return out

    def _unary_domain(self, t: TaskRequirement) -> List[Value]:
        if t.power_kW > self.cap or t.technicians > self.ntech:
            return []
        last_end = self.H if t.deadline is None else min(self.H, t.deadline)
        units = self.compatible_units(t)
        combos = list(itertools.product(*[units[r] for r in sorted(units)])) if units else [()]
        return [(s, tuple(c)) for s in range(0, last_end - t.duration + 1) for c in combos]

    def _build_neighbors(self) -> Dict[str, set]:
        nb = {k: set() for k in self.order}
        for (a, b) in self.prec:
            nb[a].add(b); nb[b].add(a)
        for pair in self.no_overlap:
            a, b = tuple(pair)
            nb[a].add(b); nb[b].add(a)
        units = {k: set(u for v in self.domains[k] for u in v[1]) for k in self.order}
        for a, b in itertools.combinations(self.order, 2):
            if units[a] & units[b]:
                nb[a].add(b); nb[b].add(a)
        return nb

    def constraint_edges(self) -> List[Tuple[str, str, str]]:
        edges = []
        for (a, b), gap in self.prec.items():
            edges.append((a, b, "separation" if gap > 0 else "precedence"))
        for pair in self.no_overlap:
            a, b = sorted(pair)
            edges.append((a, b, "no-overlap"))
        units = {k: set(u for v in self.domains[k] for u in v[1]) for k in self.order}
        for a, b in itertools.combinations(self.order, 2):
            shared = units[a] & units[b]
            if shared:
                edges.append((a, b, "resource:" + ",".join(sorted(shared))))
        return edges

    def propagate_bounds(self) -> List[str]:
        log = []
        changed = True
        while changed:
            changed = False
            for (a, b), gap in self.prec.items():
                da, db = self.domains[a], self.domains[b]
                if not da or not db:
                    continue
                est_b = min(v[0] for v in da) + self.tasks[a].duration + gap
                lst_a = max(v[0] for v in db) - gap - self.tasks[a].duration
                nb_ = [v for v in db if v[0] >= est_b]
                na_ = [v for v in da if v[0] <= lst_a]
                if len(nb_) != len(db):
                    log.append(f"bound: {b} start >= {est_b} (after {a}) |D| {len(db)}->{len(nb_)}")
                    self.domains[b] = nb_; changed = True
                if len(na_) != len(da):
                    log.append(f"bound: {a} start <= {lst_a} (before {b}) |D| {len(da)}->{len(na_)}")
                    self.domains[a] = na_; changed = True
        return log

    def prechecks(self) -> List[str]:
        problems = []
        for k in self.order:
            t = self.tasks[k]
            if t.power_kW > self.cap:
                problems.append(f"{k} draws {t.power_kW:.0f} kW > available P_res {self.cap:.1f} kW")
            if t.technicians > self.ntech:
                problems.append(f"{k} needs {t.technicians} technicians > {self.ntech}")
        est = {k: 0 for k in self.order}
        for _ in range(len(self.order)):
            for (a, b), gap in self.prec.items():
                est[b] = max(est[b], est[a] + self.tasks[a].duration + gap)
        for k in self.order:
            t = self.tasks[k]
            end = est[k] + t.duration
            limit = self.H if t.deadline is None else min(self.H, t.deadline)
            if end > limit:
                problems.append(f"critical path forces {k} to end at slot {end} > limit {limit}")
        energy = sum(t.power_kW * t.duration for t in self.tasks.values())
        if energy > self.cap * self.H + 1e-9:
            problems.append(f"energy bound: sum p*d = {energy:.0f} > P_res*H = {self.cap * self.H:.0f}")
        for k in self.order:
            if not self.domains[k]:
                problems.append(f"empty domain for {k}")
        return problems

    def _binary_ok(self, a: str, va: Value, b: str, vb: Value) -> bool:
        sa, ra = va
        sb, rb = vb
        ea, eb = sa + self.tasks[a].duration, sb + self.tasks[b].duration
        g = self.prec.get((a, b))
        if g is not None and sb < ea + g:
            return False
        g = self.prec.get((b, a))
        if g is not None and sa < eb + g:
            return False
        overlap = sa < eb and sb < ea
        if overlap and frozenset((a, b)) in self.no_overlap:
            return False
        if overlap and set(ra) & set(rb):
            return False
        return True

    def _cumulative_ok(self, k: str, v: Value, power: List[float], tech: List[int]) -> bool:
        t = self.tasks[k]
        for slot in range(v[0], v[0] + t.duration):
            if power[slot] + t.power_kW > self.cap + 1e-9:
                return False
            if tech[slot] + t.technicians > self.ntech:
                return False
        return True

    def solve(self, use_mrv=True, use_degree=True, use_fc=True,
              node_limit=300_000, trace_limit=4000) -> CSPResult:
        t0 = time.perf_counter()
        stats = {"nodes": 0, "backtracks": 0, "checks": 0, "prunes": 0, "wipeouts": 0}
        trace: List[str] = []

        def log(msg, depth):
            if len(trace) < trace_limit:
                trace.append("  " * depth + msg)

        pre = self.prechecks()
        if pre:
            for p in pre:
                log("PRECHECK FAIL: " + p, 0)
            return CSPResult(False, {}, 0, 0, 0, 0, 0, 0, trace, "; ".join(pre),
                             time.perf_counter() - t0)

        domains = {k: list(v) for k, v in self.domains.items()}
        assignment: Dict[str, Value] = {}
        power = [0.0] * (self.H + 1)
        tech = [0] * (self.H + 1)
        limit_hit = [False]

        def select_var() -> str:
            unassigned = [k for k in self.order if k not in assignment]
            if not use_mrv:
                return unassigned[0]
            def key(k):
                deg = sum(1 for n in self.neighbors[k] if n not in assignment) if use_degree else 0
                return (len(domains[k]), -deg, self.order.index(k))
            return min(unassigned, key=key)

        def consistent(k: str, v: Value) -> bool:
            for other, ov in assignment.items():
                stats["checks"] += 1
                if not self._binary_ok(k, v, other, ov):
                    return False
            stats["checks"] += 1
            return self._cumulative_ok(k, v, power, tech)

        def apply(k, v, sign):
            t = self.tasks[k]
            for slot in range(v[0], v[0] + t.duration):
                power[slot] += sign * t.power_kW
                tech[slot] += sign * t.technicians

        def fmt(k, v):
            return f"{k}=(start {v[0]}, end {v[0] + self.tasks[k].duration}, {'/'.join(v[1]) or '-'})"

        def backtrack(depth: int) -> bool:
            if len(assignment) == len(self.order):
                return True
            if stats["nodes"] >= node_limit:
                limit_hit[0] = True
                return False
            k = select_var()
            deg = sum(1 for n in self.neighbors[k] if n not in assignment)
            log(f"SELECT {k} (MRV |D|={len(domains[k])}, degree={deg})", depth)
            for v in list(domains[k]):
                stats["nodes"] += 1
                if not use_fc and not consistent(k, v):
                    continue
                if use_fc:
                    stats["checks"] += 1
                    if not self._cumulative_ok(k, v, power, tech):
                        continue
                assignment[k] = v
                apply(k, v, +1)
                log(f"ASSIGN {fmt(k, v)}", depth)
                removed = {}
                wipeout = None
                if use_fc:
                    for u in self.order:
                        if u in assignment:
                            continue
                        keep = []
                        for vu in domains[u]:
                            stats["checks"] += 2
                            if self._binary_ok(k, v, u, vu) and self._cumulative_ok(u, vu, power, tech):
                                keep.append(vu)
                        if len(keep) != len(domains[u]):
                            removed[u] = domains[u]
                            stats["prunes"] += len(domains[u]) - len(keep)
                            domains[u] = keep
                        if not keep:
                            wipeout = u
                            break
                    if removed and wipeout is None:
                        log("FC: " + ", ".join(f"{u} {len(removed[u])}->{len(domains[u])}"
                                               for u in removed), depth + 1)
                if wipeout is None and backtrack(depth + 1):
                    return True
                if wipeout is not None:
                    stats["wipeouts"] += 1
                    log(f"FC WIPEOUT: domain of {wipeout} empty -> undo {k}", depth + 1)
                for u, old in removed.items():
                    domains[u] = old
                apply(k, v, -1)
                del assignment[k]
                if limit_hit[0]:
                    return False
            stats["backtracks"] += 1
            log(f"BACKTRACK from {k}: no consistent value left", depth)
            return False

        ok = backtrack(0)
        elapsed = time.perf_counter() - t0
        if not ok:
            reason = ("node limit reached" if limit_hit[0]
                      else "search exhausted: no assignment satisfies all constraints")
            return CSPResult(False, {}, 0, stats["nodes"], stats["backtracks"], stats["checks"],
                             stats["prunes"], stats["wipeouts"], trace, reason, elapsed)
        schedule = {}
        for k in self.order:
            s, units = assignment[k]
            t = self.tasks[k]
            needs = sorted(t.needs)
            schedule[k] = {"start": s, "end": s + t.duration, "duration": t.duration,
                           "resources": dict(zip(needs, units)), "power_kW": t.power_kW,
                           "technicians": t.technicians, "name": t.name}
        makespan = max(v["end"] for v in schedule.values())
        return CSPResult(True, schedule, makespan, stats["nodes"], stats["backtracks"],
                         stats["checks"], stats["prunes"], stats["wipeouts"], trace, "", elapsed)


def solve_recovery_csp(req: Requirements, lab: LabSpec, horizon: Optional[int] = None,
                       **kw) -> Tuple[CSPResult, "RecoveryCSP", List[str]]:
    csp = RecoveryCSP(req, lab, horizon)
    bounds_log = csp.propagate_bounds()
    return csp.solve(**kw), csp, bounds_log
