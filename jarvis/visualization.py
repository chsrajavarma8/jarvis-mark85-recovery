from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
import networkx as nx

C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
GOOD, BAD = "#1a7f37", "#c62828"
FOOT = "FICTIONAL ENGINEERING SIMULATION - not measurements of a real physical system"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "axes.titleweight": "bold",
    "axes.titlesize": 11, "axes.titlecolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": False, "grid.color": GRID, "grid.linewidth": 0.6,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 160,
    "axes.spines.top": False, "axes.spines.right": False,
})


def _finish(fig, path: Path, title: str = None):
    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold", color=INK)
    fig.text(0.995, 0.005, FOOT, ha="right", va="bottom", fontsize=6.5, color=MUTED, style="italic")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _box(ax, x, y, w, h, text, fc="#f3f6fb", ec=INK2, fs=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=INK,
            fontweight="bold" if bold else "normal", wrap=True)


def _arrow(ax, p, q, text=None, color=INK2, style="-|>", ls="-", rad=0.0, fs=7.5, off=(0, 0.12)):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12, color=color, lw=1.3,
                                 linestyle=ls, connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha="center",
                va="center", fontsize=fs, color=INK2,
                bbox=dict(fc="white", ec="none", pad=0.5))


def architecture(path: Path):
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7); ax.axis("off")
    _box(ax, 2.0, 6.2, 3.7, 0.8, "FRIDAY Fault Monitor\nreactor / converter / nanite telemetry", "#fdecea", bold=True)
    _box(ax, 6.0, 6.2, 3.4, 0.8, "Shared Mission Dataset (JSON)\nnetwork, reserve, lab, deadlines", "#eef4fb", bold=True)
    _box(ax, 10.0, 6.2, 3.0, 0.8, "Tony Stark\nactivates JARVIS recovery", "#f4f4f2")
    _box(ax, 6.0, 4.9, 9.6, 0.7, "JARVIS Orchestrator  -  sequencing, data hand-off, feasibility monitoring, controlled replanning",
         "#e8f0fb", bold=True)
    _box(ax, 2.0, 3.4, 3.2, 1.3, "Stage 1  UCS\nPower Routing Engine\nmin-cost safe route\n-> power budget B, eta, theta", "#ddeaf9")
    _box(ax, 6.0, 3.4, 3.2, 1.3, "Stage 2  Simulated Annealing\nNanomaterial Optimiser\nx* under rho*B, reserve, heat\n-> P_res, repair needs", "#fde7dc")
    _box(ax, 10.0, 3.4, 3.2, 1.3, "Stage 3  CSP\nLab Scheduler\nMRV + degree + forward checking\n-> conflict-free schedule", "#dcf3ea")
    _box(ax, 3.9, 1.6, 4.0, 0.9, "Validation Engine\nindependent re-check of every constraint", "#f4f4f2", bold=True)
    _box(ax, 8.6, 1.6, 4.2, 0.9, "Visualisation + JARVIS Recovery Dashboard\nfigures, Gantt chart, status report", "#f4f4f2", bold=True)
    _box(ax, 6.0, 0.45, 5.0, 0.55, "Mark 85 armor: restored, safe, operational", "#e3f4e6", bold=True)
    _arrow(ax, (3.85, 6.2), (4.3, 6.2)); _arrow(ax, (8.5, 6.2), (7.7, 6.2))
    _arrow(ax, (6.0, 5.8), (6.0, 5.25))
    for x in (2.0, 6.0, 10.0):
        _arrow(ax, (x, 4.55), (x, 4.05))
    _arrow(ax, (3.6, 3.4), (4.4, 3.4), "B, theta", off=(0, 0.2))
    _arrow(ax, (7.6, 3.4), (8.4, 3.4), "x*, P_res", off=(0, 0.2))
    _arrow(ax, (8.4, 3.0), (7.6, 3.0), "replan: lower rho", color=C[7], ls="--", off=(0, -0.2))
    _arrow(ax, (4.4, 3.0), (3.6, 3.0), "replan: re-route", color=C[7], ls="--", off=(0, -0.2))
    _arrow(ax, (2.0, 2.75), (3.2, 2.05)); _arrow(ax, (6.0, 2.75), (4.6, 2.05)); _arrow(ax, (10.0, 2.75), (5.6, 2.0))
    _arrow(ax, (5.9, 1.6), (6.5, 1.6)); _arrow(ax, (8.6, 1.15), (6.8, 0.75))
    return _finish(fig, path, "Figure 1. JARVIS system architecture for the Mark 85 recovery mission")


NET_POS = {"ARC": (0, 0), "PC1": (1, 1.6), "PC2": (1, 0.55), "PC3": (1, -0.5), "BKP": (1, -1.6),
           "SW1": (2, 1.1), "SW2": (2, 0.0), "SW3": (2, -1.6), "BUS_A": (3, 1.6), "BUS_B": (3, 0.45),
           "BUS_C": (3, -1.0), "CLH": (4, 0.0), "FLC": (5, 1.5), "STB": (5, 0.5), "SEN": (5, -0.5),
           "LSC": (5, -1.5)}


def power_network(ds, ucs, path: Path):
    net = ds.network
    G = nx.DiGraph()
    for n in net.nodes.values():
        G.add_node(n.id)
    fig, ax = plt.subplots(figsize=(13, 7.2))
    route_edges = set(zip(ucs.path, ucs.path[1:]))
    w = net.cost_weights
    for e in net.edges:
        on = (e.u, e.v) in route_edges
        failed = net.nodes[e.u].failed or net.nodes[e.v].failed
        lowcap = e.capacity_kW < net.required_throughput_kW
        color = C[0] if on else (BAD if failed else (MUTED if lowcap else "#b9b8b3"))
        style = "dashed" if (failed or lowcap) else "solid"
        nx.draw_networkx_edges(G, NET_POS, edgelist=[(e.u, e.v)], ax=ax, edge_color=color,
                               width=3.4 if on else 1.3, style=style, arrows=True, arrowsize=14,
                               node_size=1500, connectionstyle="arc3,rad=0.0")
        (x1, y1), (x2, y2) = NET_POS[e.u], NET_POS[e.v]
        ax.text(x1 + (x2 - x1) * 0.5, y1 + (y2 - y1) * 0.5 + 0.09,
                f"c={e.cost(w):.2f}\nL{e.loss_kW:g} T{e.thermal_C:g} S{e.switch_ms:g}\ncap {e.capacity_kW:g}",
                fontsize=6.3, ha="center", va="center", color=INK if on else INK2,
                fontweight="bold" if on else "normal",
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.4))
    nx.draw_networkx_edges(G, NET_POS, edgelist=net.load_edges, ax=ax, edge_color=C[2], width=1.6,
                           style="dotted", arrows=True, arrowsize=12, node_size=1500)
    colors = []
    for n in G.nodes:
        node = net.nodes[n]
        if node.failed:
            colors.append("#f6c9c4")
        elif n in ucs.path:
            colors.append("#cfe1f7")
        elif node.type == "load":
            colors.append("#d3f1e5")
        else:
            colors.append("#f1f0ec")
    nx.draw_networkx_nodes(G, NET_POS, ax=ax, node_color=colors, node_size=1500,
                           edgecolors=[BAD if net.nodes[n].failed else INK2 for n in G.nodes], linewidths=1.4)
    nx.draw_networkx_labels(G, NET_POS, ax=ax, font_size=8, font_weight="bold")
    for n, (x, y) in NET_POS.items():
        node = net.nodes[n]
        sub = node.label + (" [FAILED]" if node.failed else "")
        ax.text(x, y - 0.27, sub, ha="center", fontsize=6.5, color=BAD if node.failed else INK2)
    for s in ds.subsystems:
        if s["id"] in NET_POS:
            x, y = NET_POS[s["id"]]
            ax.text(x + 0.33, y, f"{s['critical_load_kW']} kW", fontsize=7, va="center", color=INK2)
    legend = [Line2D([0], [0], color=C[0], lw=3.4, label=f"UCS optimal route (cost {ucs.path_cost:.2f})"),
              Line2D([0], [0], color=BAD, lw=1.3, ls="--", label="touches FAILED converter PC1"),
              Line2D([0], [0], color=MUTED, lw=1.3, ls="--", label=f"capacity < {net.required_throughput_kW:g} kW"),
              Line2D([0], [0], color="#b9b8b3", lw=1.3, label="admissible, not selected"),
              Line2D([0], [0], color=C[2], lw=1.6, ls=":", label="critical load feeders")]
    ax.legend(handles=legend, loc="lower left", fontsize=7.5, frameon=False)
    ax.text(0.0, 2.25, f"c(e) = {w['loss']}*loss[kW] + {w['thermal']}*thermal[C] + {w['switching']}*switching[ms]   |   "
            f"route thermal limit {net.thermal_limit_C:g} C   |   P_avail = {ds.reactor['available_output_kW']} kW",
            fontsize=8, color=INK2)
    ax.set_ylim(-2.2, 2.45); ax.axis("off")
    return _finish(fig, path, "Figure 2. Weighted Arc Reactor power-distribution network and UCS optimal route")


def ucs_expansion(ucs, net, path: Path):
    fig, ax = plt.subplots(figsize=(11, 4.2))
    steps = ucs.trace
    xs = [s["step"] for s in steps]; gs = [s["g"] for s in steps]
    ax.plot(xs, gs, color=C[0], lw=2, marker="o", ms=8, markeredgecolor="white", markeredgewidth=2)
    for s in steps:
        lab = s["expand"] + (" (GOAL)" if s.get("goal") else "")
        up = s["step"] % 2 == 1
        ax.annotate(f"{lab}\ng={s['g']:.2f}\nth={s['theta']:.1f}", (s["step"], s["g"]),
                    textcoords="offset points", xytext=(0, 12 if up else -14), ha="center",
                    va="bottom" if up else "top", fontsize=6.8, color=INK)
    ax.set_xlabel("Expansion step (order in which UCS pops labels from the priority queue)")
    ax.set_ylabel("Cumulative path cost g(n)")
    ax.grid(axis="y")
    ax.set_xticks(xs)
    ax.set_ylim(-14, max(gs) * 1.3)
    ax.set_yticks(range(0, int(max(gs) * 1.3) + 1, 10))
    return _finish(fig, path, "Figure 4. UCS node-expansion order with cumulative cost g(n) (non-decreasing)")


def sa_convergence(sa, path: Path):
    h = sa.history
    it = [r["iter"] for r in h]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1.4]})
    a1.plot(it, [r["cur_J"] for r in h], color=C[0], lw=1.0, alpha=0.75, label="current solution J(x)")
    a1.plot(it, [r["best_J"] for r in h], color=C[1], lw=2.0, label="best-so-far J(x*)")
    worse = [r for r in h if r["decision"].startswith("ACCEPT-WORSE")]
    a1.scatter([r["iter"] for r in worse], [r["cur_J"] for r in worse], s=9, color=C[6], zorder=3,
               label=f"accepted worse move ({len(worse)})")
    a1.set_ylabel("Readiness objective J")
    a1.grid(axis="y"); a1.legend(frameon=False, loc="lower right")
    a1.set_title(f"rho = {sa.power_fraction:.2f}, cap = {sa.power_cap_kW:.1f} kW  |  "
                 f"J: {sa.initial_objective:.2f} -> {sa.objective:.3f}  |  {sa.iterations} iterations", fontsize=9,
                 fontweight="normal", color=INK2)
    a2.plot(it, [r["T"] for r in h], color=C[3], lw=1.8)
    a2.set_yscale("log"); a2.set_ylabel("Temperature T (log)"); a2.set_xlabel("Iteration")
    a2.grid(axis="y")
    return _finish(fig, path, "Figure 6. Simulated Annealing convergence and geometric cooling schedule")


def nano_allocation(ds, attempts, final_sa, path: Path):
    cats = ds.nano.categories
    rejected = [a.sa for a in attempts if a.sa is not None and a.sa is not final_sa and a.sa.feasible]
    series = []
    if rejected:
        series.append((f"Attempt 1 (rho={rejected[0].power_fraction:.2f}) - rejected by CSP", rejected[0].allocation, C[1]))
    series.append((f"Final (rho={final_sa.power_fraction:.2f}) - committed", final_sa.allocation, C[0]))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.6, 1]})
    n = len(series); width = 0.8 / n
    for k, (lab, alloc, col) in enumerate(series):
        xs = [i + (k - (n - 1) / 2) * width for i in range(len(cats))]
        bars = a1.bar(xs, [alloc[c.id] for c in cats], width=width - 0.03, color=col, label=lab)
        for b, c in zip(bars, cats):
            a1.text(b.get_x() + b.get_width() / 2, b.get_height() + 6, str(alloc[c.id]), ha="center",
                    fontsize=7.5, color=INK)
    for i, c in enumerate(cats):
        a1.hlines(c.min_NU, i - 0.45, i + 0.45, colors=INK, linestyles="--", lw=1.2)
    a1.plot([], [], ls="--", color=INK, label="mandatory minimum")
    a1.set_xticks(range(len(cats))); a1.set_xticklabels([f"{c.id}\n" + c.name.replace(" ", "\n") for c in cats], fontsize=7.5)
    a1.set_ylabel("Nanomaterial (NU)"); a1.grid(axis="y"); a1.legend(frameon=False, fontsize=8)
    a1.set_title("Allocation per category", fontsize=10)
    used = {c.id: final_sa.allocation[c.id] for c in cats}
    rows = [("Material\n% of reserve", {c.id: 100 * used[c.id] / ds.nano.reserve_NU for c in cats},
             f"{final_sa.material_used_NU}/{ds.nano.reserve_NU} NU"),
            ("Power\n% of cap rho*B", {c.id: 100 * c.power_kW_per_NU * used[c.id] / final_sa.power_cap_kW for c in cats},
             f"{final_sa.nano_power_kW:.1f}/{final_sa.power_cap_kW:.1f} kW")]
    for y, (lab, shares, txt) in enumerate(rows):
        left = 0
        for i, c in enumerate(cats):
            a2.barh([y], [shares[c.id]], left=left, color=C[i], edgecolor="white", linewidth=2,
                    height=0.55, label=c.id if y == 0 else None)
            left += shares[c.id]
        a2.barh([y], [100 - left], left=left, color="#e9e8e4", edgecolor="white", linewidth=2, height=0.55,
                label="unused" if y == 0 else None)
        a2.text(101, y, f"{left:.1f}%\n{txt}", va="center", fontsize=8)
    a2.set_yticks([0, 1]); a2.set_yticklabels([r[0] for r in rows])
    a2.set_xlim(0, 125); a2.set_ylim(-0.6, 2.0); a2.set_xlabel("Utilisation (%)")
    a2.legend(frameon=False, fontsize=7.5, ncol=6, loc="upper center", handlelength=1.2, columnspacing=0.8)
    a2.set_title("Reserve and power-cap utilisation (final)", fontsize=10)
    return _finish(fig, path, "Figure 5. Optimised nanomaterial allocation for the damaged Mark 85")


def csp_constraint_graph(model, path: Path):
    G = nx.Graph()
    G.add_nodes_from(model.order)
    kinds = {"precedence": C[0], "separation": C[1], "no-overlap": C[7]}
    pos = nx.circular_layout(model.order)
    fig, ax = plt.subplots(figsize=(10.5, 8))
    edges = model.constraint_edges()
    for a, b, kind in edges:
        if kind.startswith("resource"):
            nx.draw_networkx_edges(G, pos, edgelist=[(a, b)], ax=ax, edge_color=MUTED, style="dashed", width=1.0)
            (x1, y1), (x2, y2) = pos[a], pos[b]
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, kind.split(":")[1], fontsize=6.3, color=INK2, ha="center",
                    bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.2))
    for a, b, kind in edges:
        if not kind.startswith("resource"):
            nx.draw_networkx_edges(nx.DiGraph([(a, b)]), pos, edgelist=[(a, b)], ax=ax, edge_color=kinds[kind],
                                   width=2.4, arrows=True, arrowstyle="-|>" if kind != "no-overlap" else "-",
                                   arrowsize=16, node_size=2600)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=2600, node_color="#eef4fb", edgecolors=INK2)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_weight="bold")
    for k, (x, y) in pos.items():
        t = model.tasks[k]
        ax.text(x, y - 0.17, f"d={t.duration}, {t.power_kW:g} kW, tech {t.technicians}", ha="center",
                fontsize=6.5, color=INK2)
    legend = [Line2D([0], [0], color=C[0], lw=2.4, label="C1 precedence  s_j >= s_i + d_i"),
              Line2D([0], [0], color=C[1], lw=2.4, label="C2 safety separation (cool-down gap)"),
              Line2D([0], [0], color=C[7], lw=2.4, label="C3 safety no-overlap"),
              Line2D([0], [0], color=MUTED, lw=1, ls="--", label="C4 potential shared resource unit"),
              Patch(fc="white", ec="white", label=f"C5/C6 global: power <= {model.cap:.1f} kW, technicians <= {model.ntech}")]
    ax.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, frameon=False, fontsize=8)
    ax.axis("off")
    return _finish(fig, path, "Figure 7. CSP constraint graph for the laboratory recovery schedule")


def gantt(csp, req, ds, path: Path, title="Figure 8. Stark Laboratory recovery schedule (Gantt chart)"):
    sch = csp.schedule
    order = sorted(sch, key=lambda k: (sch[k]["start"], sch[k]["end"]))
    H = req.horizon
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(12.5, 8.4), sharex=True,
                                     gridspec_kw={"height_ratios": [4, 1.5, 1.1]})
    for i, k in enumerate(order):
        v = sch[k]
        a1.barh(i, v["duration"], left=v["start"], height=0.62, color=C[0], edgecolor="white", linewidth=2)
        a1.text(v["end"] + 0.1, i, f"[{v['start']},{v['end']})  " + " / ".join(v["resources"].values()),
                va="center", fontsize=7, color=INK2)
    a1.set_yticks(range(len(order))); a1.set_yticklabels([f"{k}\n{sch[k]['name']}" for k in order], fontsize=7.2)
    a1.invert_yaxis(); a1.grid(axis="x")
    a1.axvline(H, color=BAD, ls="--", lw=1.2); a1.text(H - 0.1, -0.7, f"deadline H={H}", color=BAD, ha="right", fontsize=8)
    a1.axvline(csp.makespan, color=INK, ls=":", lw=1.2)
    a1.text(csp.makespan + 0.1, len(order) - 0.3, f"makespan {csp.makespan}", fontsize=8, color=INK)
    slots = list(range(H))
    pw = [sum(v["power_kW"] for v in sch.values() if v["start"] <= t < v["end"]) for t in slots]
    tc = [sum(v["technicians"] for v in sch.values() if v["start"] <= t < v["end"]) for t in slots]
    a2.bar([t + 0.5 for t in slots], pw, width=0.94, color=C[2])
    a2.axhline(req.power_cap_kW, color=BAD, ls="--", lw=1.2)
    a2.text(0.1, req.power_cap_kW * 1.04, f"P_res = {req.power_cap_kW:.1f} kW", fontsize=7.5, color=BAD, va="bottom")
    a2.set_ylim(0, req.power_cap_kW * 1.25)
    a2.set_ylabel("Lab power\n(kW)"); a2.grid(axis="y")
    a3.bar([t + 0.5 for t in slots], tc, width=0.94, color=C[6])
    a3.axhline(req.technicians, color=BAD, ls="--", lw=1.2)
    a3.set_ylabel("Technicians"); a3.set_yticks(range(req.technicians + 1)); a3.grid(axis="y")
    a3.set_xlabel(f"Time slot ({ds.mission['slot_minutes']} min each)")
    a3.set_xticks(range(H + 1)); a3.set_xlim(0, H + 4.2)
    return _finish(fig, path, title)


def workflow(out, path: Path):
    u, s, r, c = out.ucs, out.sa, out.req, out.csp
    fig, ax = plt.subplots(figsize=(13, 6.6))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6.6); ax.axis("off")
    _box(ax, 1.3, 5.6, 2.3, 1.2, "Shared dataset\nreactor 1000 kW\nreserve 1200 NU\n9 tasks, H=16", "#eef4fb", bold=True)
    _box(ax, 4.2, 5.6, 2.6, 1.2, f"STAGE 1  UCS\n{len(u.path)}-node route\ncost {u.path_cost:.2f}", "#ddeaf9", bold=True)
    _box(ax, 7.6, 5.6, 2.8, 1.2, f"STAGE 2  SA\nJ* = {s.objective:.3f}\nrho = {s.power_fraction:.2f}", "#fde7dc", bold=True)
    _box(ax, 11.3, 5.6, 2.6, 1.2, f"STAGE 3  CSP\nmakespan {c.makespan} slots\n{c.nodes} search nodes", "#dcf3ea", bold=True)
    _box(ax, 4.2, 3.4, 2.9, 1.7,
         f"UCS -> SA\nB = {u.power_budget_kW:.1f} kW\ntheta_route = {u.total_thermal_C:.1f} C\n"
         f"eta = {u.route_efficiency:.3f}\nlosses = {u.total_loss_kW:.0f} kW", "#f7f7f5")
    _box(ax, 7.6, 3.4, 3.4, 1.7,
         "SA -> CSP\n" + ", ".join(f"{k}={v}" for k, v in s.allocation.items()) +
         f"\nP_res = {s.residual_power_kW:.1f} kW\ntheta_total = {s.total_thermal_C:.2f} C\nM = {s.material_used_NU} NU",
         "#f7f7f5", fs=7.8)
    durs = "\n".join(f"{t.id}: d={t.duration}" for t in r.tasks)
    _box(ax, 11.3, 3.3, 2.7, 2.2, f"Derived CSP inputs\nP_res cap {r.power_cap_kW:.1f} kW\n" + durs,
         "#f7f7f5", fs=6.6)
    passed = sum(ch["passed"] for ch in out.checks)
    _box(ax, 6.5, 1.0, 8.4, 1.0, f"Validation: {passed}/{len(out.checks)} checks passed  ->  {out.status}",
         "#e3f4e6" if out.success else "#fdecea", bold=True)
    _arrow(ax, (2.45, 5.6), (2.9, 5.6)); _arrow(ax, (5.5, 5.6), (6.2, 5.6)); _arrow(ax, (9.0, 5.6), (10.0, 5.6))
    _arrow(ax, (4.2, 5.0), (4.2, 4.25)); _arrow(ax, (5.65, 4.0), (6.6, 5.0), "B, theta, eta", off=(-0.35, 0.05))
    _arrow(ax, (7.6, 5.0), (7.6, 4.25)); _arrow(ax, (9.3, 3.4), (9.95, 3.4)); _arrow(ax, (11.3, 4.25), (11.3, 5.0))
    _arrow(ax, (10.0, 6.25), (9.0, 6.25), "CSP infeasible -> lower rho", color=C[7], ls="--", rad=-0.0, off=(0, 0.2))
    _arrow(ax, (6.3, 6.35), (5.5, 6.35), "SA infeasible -> re-route", color=C[7], ls="--", off=(0, 0.17))
    _arrow(ax, (11.3, 2.55), (8.8, 1.5)); _arrow(ax, (4.2, 2.55), (5.0, 1.5)); _arrow(ax, (7.6, 2.55), (7.0, 1.5))
    return _finish(fig, path, "Figure 3. End-to-end workflow and data exchanged between UCS, SA and CSP")


def dashboard(ds, out, path: Path):
    u, s, r, c = out.ucs, out.sa, out.req, out.csp
    fig = plt.figure(figsize=(15, 9.6))
    gs = fig.add_gridspec(3, 3, height_ratios=[0.5, 1.6, 1.7], hspace=0.55, wspace=0.32)
    banner = fig.add_subplot(gs[0, :]); banner.axis("off")
    banner.add_patch(FancyBboxPatch((0, 0.05), 1, 0.9, boxstyle="round,pad=0.01", transform=banner.transAxes,
                                    fc="#e3f4e6" if out.success else "#fdecea", ec=GOOD if out.success else BAD, lw=2))
    passed = sum(ch["passed"] for ch in out.checks)
    banner.text(0.5, 0.62, f"JARVIS RECOVERY STATUS: {out.status}", ha="center", va="center", fontsize=15,
                fontweight="bold", transform=banner.transAxes, color=INK)
    banner.text(0.5, 0.25, f"Mission {ds.mission['id']}  |  route {' > '.join(u.path)}  |  power cost {u.path_cost:.2f}  |  "
                f"{passed}/{len(out.checks)} constraint checks PASS  |  replanning attempts {len(out.attempts)}  |  "
                f"completion {c.makespan * ds.mission['slot_minutes'] / 60:.1f} h",
                ha="center", va="center", fontsize=9.5, transform=banner.transAxes, color=INK2)

    a = fig.add_subplot(gs[1, 0])
    P = ds.reactor["available_output_kW"]
    labels = ["Reactor available", "Route losses", "Bottleneck curtailment", "Delivered to CLH", "Critical loads",
              "Nanomaterial (SA)", "Peak lab ops (CSP)", "Unused margin"]
    peak = max(sum(v["power_kW"] for v in c.schedule.values() if v["start"] <= t < v["end"]) for t in range(r.horizon))
    vals = [P, u.total_loss_kW, P - u.total_loss_kW - u.delivered_power_kW, u.delivered_power_kW,
            u.critical_load_kW, s.nano_power_kW, peak,
            u.delivered_power_kW - u.critical_load_kW - s.nano_power_kW - peak]
    cols = [C[0], C[7], C[3], C[0], C[2], C[1], C[6], "#bdbcb7"]
    a.barh(range(len(vals)), vals, color=cols, edgecolor="white", linewidth=2)
    for i, v in enumerate(vals):
        a.text(v + 8, i, f"{v:.1f} kW", va="center", fontsize=7.5)
    a.set_yticks(range(len(vals))); a.set_yticklabels(labels, fontsize=8); a.invert_yaxis()
    a.set_xlim(0, P * 1.3); a.set_title("Power budget chain (kW)", fontsize=10); a.grid(axis="x")

    a = fig.add_subplot(gs[1, 1])
    cats = ds.nano.categories
    a.bar([cc.id for cc in cats], [s.allocation[cc.id] for cc in cats], color=C[0], width=0.6)
    for i, cc in enumerate(cats):
        a.hlines(cc.min_NU, i - 0.35, i + 0.35, colors=INK, linestyles="--", lw=1)
        a.text(i, s.allocation[cc.id] + 8, str(s.allocation[cc.id]), ha="center", fontsize=8)
    a.set_title(f"Nanomaterial allocation ({s.material_used_NU}/{ds.nano.reserve_NU} NU, dashed = minimum)", fontsize=10)
    a.grid(axis="y")

    a = fig.add_subplot(gs[1, 2])
    subs = ds.subsystems
    xs = range(len(subs))
    a.bar([i - 0.2 for i in xs], [q["health_pct"] for q in subs], width=0.38, color=C[1], label="before (FRIDAY)")
    a.bar([i + 0.2 for i in xs], [out.health_after[q["id"]] for q in subs], width=0.38, color=C[0],
          label="after (model estimate)")
    a.set_xticks(list(xs)); a.set_xticklabels([q["id"] for q in subs]); a.set_ylim(0, 115)
    a.set_title("Subsystem health (%)", fontsize=10); a.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left")
    a.grid(axis="y")

    a = fig.add_subplot(gs[2, :2])
    sch = c.schedule
    order = sorted(sch, key=lambda k: (sch[k]["start"], sch[k]["end"]))
    for i, k in enumerate(order):
        a.barh(i, sch[k]["duration"], left=sch[k]["start"], color=C[0], edgecolor="white", linewidth=2, height=0.7)
        a.text(sch[k]["start"] + 0.08, i, k, va="center", fontsize=7, color="white", fontweight="bold")
    a.set_yticks([]); a.invert_yaxis(); a.set_xlim(0, r.horizon); a.set_xticks(range(r.horizon + 1))
    a.axvline(r.horizon, color=BAD, ls="--"); a.grid(axis="x")
    a.set_title(f"Repair schedule (makespan {c.makespan} of {r.horizon} slots)", fontsize=10)

    a = fig.add_subplot(gs[2, 2]); a.axis("off")
    stages = ["UCS", "SA", "CSP", "INTEGRATED"]
    y = 0.98
    a.text(0, y, "Constraint validation", fontsize=10, fontweight="bold", transform=a.transAxes)
    for st in stages:
        cs = [ch for ch in out.checks if ch["stage"] == st]
        ok = sum(ch["passed"] for ch in cs)
        y -= 0.1
        a.text(0, y, f"{st:<11} {ok}/{len(cs)} PASS" if ok == len(cs) else f"{st:<11} {ok}/{len(cs)} - FAIL",
               fontsize=9.5, family="monospace", color=GOOD if ok == len(cs) else BAD, transform=a.transAxes,
               fontweight="bold")
    y -= 0.12
    for line in [f"Route cost      {u.path_cost:.2f}", f"Delivered       {u.delivered_power_kW:.1f} kW",
                 f"Budget B        {u.power_budget_kW:.1f} kW", f"Nano power      {s.nano_power_kW:.1f} kW",
                 f"Residual P_res  {s.residual_power_kW:.1f} kW", f"Thermal total   {s.total_thermal_C:.2f} C",
                 f"Objective J*    {s.objective:.3f}"]:
        a.text(0, y, line, fontsize=8.5, family="monospace", transform=a.transAxes); y -= 0.075
    return _finish(fig, path, "Figure 9. JARVIS recovery dashboard - Mark 85")


def performance(perf: dict, path: Path):
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.6))
    sa, hc = perf["sa_vs_hc"]["sa"], perf["sa_vs_hc"]["hc"]
    bp = a1.boxplot([sa, hc], tick_labels=["Simulated\nAnnealing", "Hill climbing\n(T = 0)"], widths=0.5,
                    patch_artist=True, medianprops=dict(color=INK, lw=1.6))
    for patch, col in zip(bp["boxes"], [C[0], C[1]]):
        patch.set_facecolor(col); patch.set_alpha(0.85)
    a1.set_ylabel("Final objective J"); a1.grid(axis="y")
    a1.set_title(f"SA vs hill climbing, {len(sa)} seeds", fontsize=10)
    rows = perf["csp_variants"]
    names = [r["variant"] for r in rows]
    a2.barh(names, [r["nodes"] for r in rows], color=C[2])
    a2.set_xscale("log"); a2.set_xlabel("Search nodes (log scale)"); a2.invert_yaxis()
    for i, r in enumerate(rows):
        a2.text(r["nodes"] * 1.15, i, f"{r['nodes']} nodes, {r['backtracks']} bt", va="center", fontsize=7.5)
    a2.set_title("CSP search effort by heuristic set", fontsize=10); a2.grid(axis="x")
    a2.set_xlim(1, max(r["nodes"] for r in rows) * 40)
    rows = perf["route_methods"]
    a3.bar([r["method"] for r in rows], [r["cost"] for r in rows], color=[C[0] if r["feasible"] else "#bdbcb7" for r in rows])
    for i, r in enumerate(rows):
        a3.text(i, r["cost"] + 0.8, f"{r['cost']:.2f}\n{'feasible' if r['feasible'] else 'VIOLATES'}", ha="center",
                fontsize=7.5)
    a3.set_ylabel("Route cost"); a3.set_title("Route found by each search strategy", fontsize=10)
    a3.tick_params(axis="x", labelsize=7.5); a3.grid(axis="y")
    a3.set_ylim(0, max(r["cost"] for r in rows) * 1.25)
    return _finish(fig, path, "Figure 10. Performance analysis of the three stages")
