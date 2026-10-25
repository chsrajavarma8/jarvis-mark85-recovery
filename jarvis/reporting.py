from __future__ import annotations

import csv
import json
from pathlib import Path

from .data_models import to_jsonable


def rule(title="", ch="="):
    return f"\n{ch * 78}\n{title}\n{ch * 78}" if title else ch * 78


def mission_header(ds) -> str:
    lines = [rule("JARVIS :: MARK 85 INTELLIGENT RECOVERY  (fictional engineering simulation)"),
             f"Mission          : {ds.mission['id']} at {ds.mission['location']}",
             f"Trigger          : {ds.mission['trigger']}",
             f"Arc Reactor      : {ds.reactor['available_output_kW']} kW available of "
             f"{ds.reactor['nominal_output_kW']} kW nominal ({ds.reactor['status']})",
             f"Critical load    : {ds.critical_load_kW:.0f} kW  (FLC+STB+SEN+LSC)",
             f"Nanomaterial     : {ds.nano.reserve_NU} NU reserve, armor thermal limit "
             f"{ds.nano.armor_thermal_limit_C} C",
             f"Laboratory       : {len(ds.lab.tasks)} tasks, {ds.lab.technicians} technicians, horizon "
             f"{ds.mission['horizon_slots']} x {ds.mission['slot_minutes']} min", "",
             "Subsystem status reported by FRIDAY:"]
    for s in ds.subsystems:
        lines.append(f"  {s['id']:<4} {s['name']:<26} health {s['health_pct']:>3}%  load "
                     f"{s['critical_load_kW']:>4} kW  {s['status']}")
    return "\n".join(lines)


def ucs_report(ds, u) -> str:
    net = ds.network
    L = [rule("STAGE 1 - UNIFORM COST SEARCH: Arc Reactor power routing"),
         f"Edge cost c(e) = {net.cost_weights['loss']}*loss + {net.cost_weights['thermal']}*thermal + "
         f"{net.cost_weights['switching']}*switching ; P_req = {net.required_throughput_kW:g} kW ; "
         f"Theta_max = {net.thermal_limit_C:g} C", "",
         f"{'edge':<14}{'loss kW':>8}{'therm C':>9}{'sw ms':>7}{'cap kW':>8}{'cost':>8}"]
    for e in net.edges:
        L.append(f"{e.u + '->' + e.v:<14}{e.loss_kW:>8g}{e.thermal_C:>9g}{e.switch_ms:>7g}"
                 f"{e.capacity_kW:>8g}{e.cost(net.cost_weights):>8.2f}")
    L.append("\nExpansion trace (frontier shown as node:g/theta, ordered by g):")
    for s in u.trace:
        L.append(f" step {s['step']:>2}: expand {s['expand']:<6} g={s['g']:>6.2f} theta={s['theta']:>5.1f} "
                 f"path={'>'.join(s['path'])}{'   <-- GOAL' if s.get('goal') else ''}")
        for p in s["pushed"]:
            L.append(f"          push {p['to']:<6} g={p['g']:>6.2f} theta={p['theta']:>5.1f} (edge {p['edge_cost']})")
        for r in s["rejected"]:
            L.append(f"          reject {r['to']:<6} {r['reason']}")
        L.append("          frontier: " + ", ".join(f"{f['node']}:{f['g']}/{f['theta']}" for f in s["frontier_after"]))
    L += ["", f"OPTIMAL ROUTE   : {' -> '.join(u.path)}",
          f"path cost g*    : {u.path_cost:.2f}",
          f"losses / thermal / switching : {u.total_loss_kW:g} kW / {u.total_thermal_C:g} C / {u.total_switch_ms:g} ms",
          f"bottleneck cap  : {u.bottleneck_capacity_kW:g} kW",
          f"delivered power : min({ds.reactor['available_output_kW']} - {u.total_loss_kW:g}, "
          f"{u.bottleneck_capacity_kW:g}) = {u.delivered_power_kW:g} kW",
          f"power budget B  : {u.delivered_power_kW:g} - {u.critical_load_kW:g} = {u.power_budget_kW:g} kW  -> Stage 2",
          f"route efficiency eta = {u.route_efficiency:.3f}  -> Stage 3 charging rate",
          f"expanded {u.expansions} labels, generated {u.generated}"]
    return "\n".join(L)


def sa_report(ds, s, show=25) -> str:
    L = [rule("STAGE 2 - SIMULATED ANNEALING: nanomaterial allocation"),
         f"power cap rho*B = {s.power_fraction:.2f} x {s.power_cap_kW / s.power_fraction:.1f} = {s.power_cap_kW:.1f} kW",
         f"initial (mandatory minimums) {s.initial_allocation}  J0 = {s.initial_objective:.3f}", "",
         f"{'iter':>5} {'T':>8} {'move':<24}{'cand J':>9}{'dE':>9}{'P(acc)':>8}  decision"]
    rows = s.history[1:show + 1] + [None] + [r for r in s.history if r["iter"] % 400 == 0 and r["iter"] > show]
    for r in rows:
        if r is None:
            L.append("  ...  (every 400th iteration below)")
            continue
        cj = f"{r['cand_J']:.3f}" if r["cand_J"] is not None else "-"
        de = f"{r['dE']:+.3f}" if r["dE"] is not None else "-"
        L.append(f"{r['iter']:>5} {r['T']:>8.4f} {r['move']:<24}{cj:>9}{de:>9}{r['p_accept']:>8.3f}  {r['decision']}")
    L += ["", f"termination     : {s.termination}",
          f"iterations {s.iterations}, accepted-worse {s.accepted_worse}, rejected-infeasible neighbours "
          f"{s.rejected_infeasible}, best improvements {s.improvements}",
          f"BEST ALLOCATION : {s.allocation}",
          f"objective J*    : {s.objective:.4f}  (from {s.initial_objective:.4f})",
          f"material used   : {s.material_used_NU} / {ds.nano.reserve_NU} NU",
          f"nano power      : {s.nano_power_kW:.1f} kW (cap {s.power_cap_kW:.1f})",
          f"residual P_res  : {s.residual_power_kW:.1f} kW  -> Stage 3 power constraint",
          f"total thermal   : {s.total_thermal_C:.2f} C (limit {ds.nano.armor_thermal_limit_C})"]
    return "\n".join(L)


def csp_report(out, trace_lines=60) -> str:
    r, c = out.req, out.csp
    L = [rule("STAGE 3 - CSP: Stark Laboratory recovery scheduling"), "Derived inputs:"]
    L += ["  " + n for n in r.notes]
    L.append(f"\n{'task':<14}{'dur':>4}{'kW':>6}{'tech':>5}  needs / after / derivation")
    for t in r.tasks:
        L.append(f"{t.id:<14}{t.duration:>4}{t.power_kW:>6g}{t.technicians:>5}  "
                 f"{t.needs} after={t.after or '-'} dl={t.deadline}  [{t.derivation}]")
    L.append("\nInitial domain sizes (after unary + bound propagation):")
    L.append("  " + ", ".join(f"{k}:{len(v)}" for k, v in out.csp_model.domains.items()))
    for b in out.bounds_log:
        L.append("  " + b)
    L.append("\nSearch trace (first solve):")
    L += ["  " + x for x in out.csp_first.trace[:trace_lines]]
    L.append(f"\nfirst solve: nodes={out.csp_first.nodes} backtracks={out.csp_first.backtracks} "
             f"checks={out.csp_first.constraint_checks} FC-prunes={out.csp_first.fc_prunes} "
             f"wipeouts={out.csp_first.wipeouts} makespan={out.csp_first.makespan}")
    L.append("Makespan tightening:")
    for m in out.makespan_search:
        L.append(f"  H={m['horizon']:>2}: {'solved' if m['solved'] else 'infeasible'} ({m['reason']})")
    L.append(f"\nFINAL SCHEDULE (makespan {c.makespan} slots):")
    L.append(f"{'task':<14}{'start':>6}{'end':>5}  resources")
    for k, v in sorted(c.schedule.items(), key=lambda kv: (kv[1]["start"], kv[0])):
        L.append(f"{k:<14}{v['start']:>6}{v['end']:>5}  {v['resources']}")
    return "\n".join(L)


def attempts_report(out) -> str:
    L = [rule("CONTROLLED REPLANNING LOG")]
    for a in out.attempts:
        L.append(f"attempt {a.number}: rho={a.power_fraction:.2f} excluded={a.excluded_edges or '-'}")
        if a.ucs and a.ucs.found:
            L.append(f"   UCS route {' > '.join(a.ucs.path)}  B={a.ucs.power_budget_kW:.1f} kW")
        if a.sa and a.sa.feasible:
            L.append(f"   SA  {a.sa.allocation} J={a.sa.objective:.3f} P_res={a.sa.residual_power_kW:.1f} kW")
        L.append(f"   outcome: {a.outcome}")
        L.append(f"   action : {a.action}")
    return "\n".join(L)


def validation_report(out) -> str:
    L = [rule("INTEGRATED VALIDATION")]
    for ch in out.checks:
        L.append(f"[{'PASS' if ch['passed'] else 'FAIL'}] {ch['stage']:<10} {ch['check']:<55} {ch['detail']}")
    passed = sum(c["passed"] for c in out.checks)
    L += ["", f"{passed}/{len(out.checks)} checks passed", "Estimated post-recovery health (model): " +
          ", ".join(f"{k} {v}%" for k, v in out.health_after.items()),
          rule(f"FINAL ARMOR STATUS: {out.status}")]
    return "\n".join(L)


def export(out, ds, perf, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    s = out.sa
    with open(outdir / "sa_iterations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iter", "T", "move", "cand_J", "dE", "p_accept", "decision", "cur_J", "best_J"] +
                   [c.id for c in ds.nano.categories])
        for r in s.history:
            w.writerow([r["iter"], f"{r['T']:.6f}", r["move"], r["cand_J"], r["dE"], f"{r['p_accept']:.5f}",
                        r["decision"], f"{r['cur_J']:.5f}", f"{r['best_J']:.5f}"] +
                       [r["alloc"][c.id] for c in ds.nano.categories])
    with open(outdir / "schedule.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["task", "name", "start", "end", "duration", "power_kW", "technicians", "resources"])
        for k, v in sorted(out.csp.schedule.items(), key=lambda kv: kv[1]["start"]):
            w.writerow([k, v["name"], v["start"], v["end"], v["duration"], v["power_kW"], v["technicians"],
                        "; ".join(f"{a}={b}" for a, b in v["resources"].items())])
    with open(outdir / "validation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "check", "passed", "detail"])
        w.writeheader(); w.writerows(out.checks)
    (outdir / "csp_trace.txt").write_text("\n".join(out.csp_first.trace), encoding="utf-8")
    summary = {
        "status": out.status, "success": out.success,
        "attempts": [{"number": a.number, "rho": a.power_fraction, "excluded": a.excluded_edges,
                      "outcome": a.outcome, "action": a.action,
                      "route": a.ucs.path if a.ucs else None,
                      "allocation": a.sa.allocation if a.sa else None,
                      "objective": a.sa.objective if a.sa else None,
                      "residual_power_kW": a.sa.residual_power_kW if a.sa else None,
                      "durations": {t.id: t.duration for t in a.req.tasks} if a.req else None}
                     for a in out.attempts],
        "ucs": {k: v for k, v in to_jsonable(out.ucs).items() if k not in ("trace",)},
        "ucs_trace": out.ucs.trace,
        "sa": {k: v for k, v in to_jsonable(out.sa).items() if k != "history"},
        "requirements": to_jsonable(out.req),
        "csp_first": {k: v for k, v in to_jsonable(out.csp_first).items() if k != "trace"},
        "csp_final": {k: v for k, v in to_jsonable(out.csp).items() if k != "trace"},
        "csp_domains": {k: len(v) for k, v in out.csp_model.domains.items()},
        "csp_bounds_log": out.bounds_log,
        "csp_constraint_edges": out.csp_model.constraint_edges(),
        "makespan_search": out.makespan_search,
        "checks": out.checks, "health_after": out.health_after,
        "performance": perf,
    }
    (outdir / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
