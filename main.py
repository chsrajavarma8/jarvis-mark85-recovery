from __future__ import annotations

import argparse
import io
import sys
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path

from jarvis import reporting, visualization as viz
from jarvis.data_models import load_dataset
from jarvis.experiments import run_experiments
from jarvis.pipeline import run_mission

ROOT = Path(__file__).resolve().parent


def _rel(p) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="JARVIS Mark 85 recovery mission")
    ap.add_argument("--dataset", default=str(ROOT / "data" / "mission_dataset.json"))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--seed", type=int, default=None, help="override the dataset random seed")
    ap.add_argument("--no-plots", action="store_true")
    ap.add_argument("--quick", action="store_true", help="skip the multi-seed performance study")
    ap.add_argument("--scenario", choices=["nominal", "pc2-failure"], default="nominal",
                    help="pc2-failure: stress test in which the secondary converter also fails")
    args = ap.parse_args(argv)

    outdir = Path(args.out)
    figdir = outdir / "figures"
    outdir.mkdir(parents=True, exist_ok=True)
    log_buffer = io.StringIO()
    tee = Tee(sys.stdout, log_buffer)

    with redirect_stdout(tee):
        ds = load_dataset(args.dataset)
        if args.scenario == "pc2-failure":
            ds.network.nodes["PC2"] = replace(ds.network.nodes["PC2"], status="FAILED")
            print("STRESS SCENARIO: FRIDAY reports secondary converter PC2 FAILED as well")
        print(reporting.mission_header(ds))
        out = run_mission(ds, seed=args.seed)
        if out.ucs is None or out.csp is None or not out.csp.solved:
            print(reporting.attempts_report(out))
            print(f"\nMISSION FAILED: {out.status}")
            (outdir / "console_log.txt").write_text(log_buffer.getvalue(), encoding="utf-8")
            return 2
        print(reporting.ucs_report(ds, out.ucs))
        print(reporting.sa_report(ds, out.sa))
        print(reporting.csp_report(out))
        print(reporting.attempts_report(out))
        print(reporting.validation_report(out))

        perf = {}
        if not args.quick:
            print(reporting.rule("PERFORMANCE STUDY"))
            perf = run_experiments(ds, out)
            sv = perf["sa_vs_hc"]
            print(f"SA  over {len(sv['sa'])} seeds: mean J={sv['sa_mean']:.3f} sd={sv['sa_std']:.3f} "
                  f"best={sv['sa_best']:.3f} worst={sv['sa_worst']:.3f}")
            print(f"HC  over {len(sv['hc'])} seeds: mean J={sv['hc_mean']:.3f} sd={sv['hc_std']:.3f} "
                  f"best={sv['hc_best']:.3f} worst={sv['hc_worst']:.3f}   SA better in {sv['sa_wins']} seeds")
            for r in perf["csp_variants"]:
                print(f"CSP {r['variant']:<24} solved={r['solved']} nodes={r['nodes']:>6} "
                      f"backtracks={r['backtracks']:>6} checks={r['checks']:>7} time={r['time_ms']} ms")
            for r in perf["route_methods"]:
                print(f"ROUTE {r['method'].replace(chr(10), ' '):<30} {' > '.join(r['path'])} cost={r['cost']} "
                      f"thermal={r['thermal']} feasible={r['feasible']}")
            print(f"timing (ms): {perf['timing_ms']}")

        reporting.export(out, ds, perf, outdir)
        if not args.no_plots:
            figdir.mkdir(parents=True, exist_ok=True)
            figs = [viz.architecture(figdir / "fig01_architecture.png"),
                    viz.power_network(ds, out.ucs, figdir / "fig02_power_network.png"),
                    viz.ucs_expansion(out.ucs, ds.network, figdir / "fig03_ucs_expansion.png"),
                    viz.nano_allocation(ds, out.attempts, out.sa, figdir / "fig04_nano_allocation.png"),
                    viz.sa_convergence(out.sa, figdir / "fig05_sa_convergence.png"),
                    viz.csp_constraint_graph(out.csp_model, figdir / "fig06_csp_constraint_graph.png"),
                    viz.gantt(out.csp, out.req, ds, figdir / "fig07_gantt.png"),
                    viz.workflow(out, figdir / "fig08_workflow.png"),
                    viz.dashboard(ds, out, figdir / "fig09_dashboard.png")]
            if perf:
                figs.append(viz.performance(perf, figdir / "fig10_performance.png"))
            print(reporting.rule("FIGURES"))
            for f in figs:
                print("  " + _rel(f))
        print(f"\nExports written to {_rel(outdir)}")
    (outdir / "console_log.txt").write_text(log_buffer.getvalue(), encoding="utf-8")
    return 0 if out.success else 1


if __name__ == "__main__":
    sys.exit(main())
