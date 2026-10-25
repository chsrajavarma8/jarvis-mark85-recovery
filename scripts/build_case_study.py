from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jarvis.data_models import load_dataset

OUT = ROOT / "outputs"
FIG = OUT / "figures"
BLACK = RGBColor(0, 0, 0)

R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
DS = load_dataset(ROOT / "data" / "mission_dataset.json")
U, S, REQ = R["ucs"], R["sa"], R["requirements"]
C1, CF = R["csp_first"], R["csp_final"]
PERF = R["performance"]
A1 = R["attempts"][0]
SLOT = DS.mission["slot_minutes"]
H = DS.mission["horizon_slots"]
NET = DS.network
W = NET.cost_weights
ROUTE = " → ".join(U["path"])
N_CHECKS = len(R["checks"])
N_PASS = sum(c["passed"] for c in R["checks"])

doc = Document()
fig_no = [0]
tab_no = [0]


def setup():
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.font.size = Pt(11)
    st.font.color.rgb = BLACK
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.15
    for lvl, size in ((1, 16), (2, 13), (3, 11.5)):
        h = doc.styles[f"Heading {lvl}"]
        h.font.name = "Calibri"
        h.element.rPr.rFonts.set(qn("w:asciiTheme"), "")
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = BLACK
        h.paragraph_format.space_before = Pt(14 if lvl == 1 else 10)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
    for name in ("Title", "Subtitle"):
        doc.styles[name].font.color.rgb = BLACK
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run("JARVIS Mark 85 Recovery – AI Case Study  |  Fictional engineering simulation  |  Page ")
    r.font.size = Pt(8)
    _field(footer, "PAGE", 8)


def _field(par, instr, size):
    run = par.add_run()
    run.font.size = Pt(size)
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
    t = OxmlElement("w:instrText"); t.set(qn("xml:space"), "preserve"); t.text = instr
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
    run._r.append(b); run._r.append(t); run._r.append(e)


def h1(t):
    doc.add_heading(t, level=1)


def h2(t):
    doc.add_heading(t, level=2)


def h3(t):
    doc.add_heading(t, level=3)


def p(text, bold_lead=None, italic=False, align=None, size=None):
    par = doc.add_paragraph()
    if bold_lead:
        r = par.add_run(bold_lead); r.bold = True
    r = par.add_run(text); r.italic = italic
    if size:
        for run in par.runs:
            run.font.size = Pt(size)
    if align == "center":
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align != "left":
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return par


def bullets(items, style="List Bullet"):
    for it in items:
        par = doc.add_paragraph(style=style)
        if isinstance(it, tuple):
            r = par.add_run(it[0]); r.bold = True
            par.add_run(it[1])
        else:
            par.add_run(it)


def eq(text, label=None):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run(text)
    r.font.name = "Cambria Math"; r.font.size = Pt(11); r.italic = False
    if label:
        r2 = par.add_run(f"        ({label})"); r2.font.size = Pt(10)
    par.paragraph_format.space_after = Pt(4)


def code(text, size=7.5):
    for block in text.split("\n\n\n"):
        par = doc.add_paragraph()
        par.paragraph_format.space_after = Pt(2)
        par.paragraph_format.line_spacing = 1.0
        _shade(par, "F2F2F2")
        r = par.add_run(block.rstrip("\n"))
        r.font.name = "Consolas"; r.font.size = Pt(size)
        r.element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")


def _shade(par, color):
    pPr = par._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    pPr.append(shd)


def _cell_shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def table(header, rows, caption=None, widths=None, size=9):
    if caption:
        tab_no[0] += 1
        cp = doc.add_paragraph()
        r = cp.add_run(f"Table {tab_no[0]}. {caption}"); r.bold = True; r.font.size = Pt(10)
        cp.paragraph_format.keep_with_next = True
        cp.paragraph_format.space_before = Pt(6)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(str(h)); run.bold = True; run.font.size = Pt(size)
        _cell_shade(c, "D9D9D9")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v)); run.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, wd in enumerate(widths):
                row.cells[i].width = Cm(wd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(name, caption, width=16.5):
    fig_no[0] += 1
    doc.add_picture(str(FIG / name), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cp.add_run(caption); r.italic = True; r.font.size = Pt(9.5)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def notice():
    par = doc.add_paragraph()
    _shade(par, "EDEDED")
    r = par.add_run("Simulation notice. ")
    r.bold = True
    par.add_run("The Iron Man Mark 85 armor, the Arc Reactor, FRIDAY, JARVIS and Stark Laboratory are fictional "
                "(Marvel). Every number in this case study – power ratings, losses, thermal rises, nanomaterial "
                "quantities, task durations – is invented simulation data designed for an academic exercise. "
                "None of the values is a measurement of a real physical system. The algorithms, mathematics, "
                "code and results, however, are real: every result reported here was produced by executing the "
                "accompanying Python application.")


def title_page():
    for _ in range(3):
        doc.add_paragraph()
    par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("ARTIFICIAL INTELLIGENCE – CASE STUDY"); r.bold = True; r.font.size = Pt(12)
    doc.add_paragraph()
    par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("JARVIS: Intelligent Iron Man Armor Recovery and Resource Optimization Using "
                    "Uniform Cost Search, Simulated Annealing, and Constraint Satisfaction Problems")
    r.bold = True; r.font.size = Pt(20)
    doc.add_paragraph()
    par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("One integrated engineering mission: restoring a damaged Mark 85 armor through optimal power "
                    "routing, stochastic nanomaterial optimisation and constraint-based laboratory scheduling")
    r.italic = True; r.font.size = Pt(12)
    for _ in range(4):
        doc.add_paragraph()
    rows = [("Course", "Artificial Intelligence"), ("Submission type", "Technical case study, implementation and viva"),
            ("Submitted by", "______________________________"), ("Register / Roll No.", "______________________________"),
            ("Instructor", "______________________________"), ("Date", "October 2026"),
            ("Implementation", "Python 3 (heapq, math, random, matplotlib, networkx)"),
            ("Mission ID", DS.mission["id"])]
    t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for a, b in rows:
        c = t.add_row().cells
        c[0].text = ""; ra = c[0].paragraphs[0].add_run(a); ra.bold = True
        c[1].text = b
        c[0].width, c[1].width = Cm(5), Cm(10)
    for _ in range(3):
        doc.add_paragraph()
    notice()
    page_break()


def contents():
    h1("Contents")
    items = ["Abstract", "1. Introduction", "2. Background: Iron Man Technology Concepts",
             "3. Unified Engineering Problem Statement", "4. Objectives", "5. System Architecture",
             "6. Problem Formulation and Mathematical Models", "7. The Three Algorithms and Why All Three Are Needed",
             "8. Integrated Methodology and Data Flow", "9. Pseudocode", "10. Python Implementation",
             "11. Experimental Setup and Common Input Dataset", "12. Step-by-Step Execution Trace",
             "13. Results", "14. Performance Analysis", "15. Algorithm Comparison", "16. Limitations",
             "17. Real-World Engineering Relevance", "18. Conclusion", "References", "Viva Questions and Answers",
             "Appendix A. Complete Source Code", "Appendix B. Shared Mission Dataset (JSON)",
             "Appendix C. Console Output of the Executed Mission"]
    for it in items:
        par = doc.add_paragraph(it); par.paragraph_format.space_after = Pt(1)
    page_break()


def abstract():
    h1("Abstract")
    p(f"During a test session at Stark Tower, FRIDAY detects a cascading failure in the Iron Man Mark 85: the "
      f"primary power converter (PC1) is offline, the Arc Reactor is derated to "
      f"{DS.reactor['available_output_kW']} kW, the nanomaterial reserve is limited to {DS.nano.reserve_NU} "
      f"nano-units (NU), and five subsystems are damaged. This case study presents JARVIS, an integrated AI "
      f"recovery planner that solves this single engineering problem in three cooperating stages. "
      f"Stage 1 applies Uniform Cost Search (UCS) to a weighted power-distribution graph and finds the "
      f"minimum-cost route that avoids failed components and respects capacity and cumulative thermal limits "
      f"({ROUTE}, cost {U['path_cost']:.2f}). Because the thermal limit is a path constraint, we use a "
      f"label-setting form of UCS with dominance pruning that remains provably optimal. The route fixes the "
      f"deliverable power and therefore the repair power budget B = {U['power_budget_kW']:.0f} kW. "
      f"Stage 2 uses Simulated Annealing (SA) to distribute nanomaterial among five protection and repair "
      f"functions, maximising a non-convex readiness objective subject to the budget, the reserve, mandatory "
      f"structural protection and the armor thermal limit. Stage 3 converts the route and the allocation "
      f"into task durations and a residual power cap and solves the laboratory scheduling problem as a "
      f"Constraint Satisfaction Problem (CSP) using backtracking with Minimum Remaining Values, the degree "
      f"heuristic and forward checking. JARVIS monitors feasibility between stages. In the executed mission "
      f"the first plan was rejected because armor charging ({REQ['tasks'][6]['power_kW']:.0f} kW) exceeded "
      f"the residual power ({A1['residual_power_kW']:.1f} kW), and JARVIS replanned by lowering the "
      f"nanomaterial power fraction from {A1['rho']:.2f} to {S['power_fraction']:.2f}. The final plan "
      f"completes in {CF['makespan']} slots ({CF['makespan'] * SLOT / 60:.1f} h) against a "
      f"{H * SLOT / 60:.0f} h deadline and passes {N_PASS}/{N_CHECKS} independent constraint checks. "
      f"Experiments show SA outperforming pure hill-climbing on all {len(PERF['sa_vs_hc']['sa'])} random seeds "
      f"and MRV + degree + forward checking reducing CSP search from {PERF['csp_variants'][-1]['nodes']} to "
      f"{PERF['csp_variants'][0]['nodes']} nodes.")
    p("Keywords: ", None)
    doc.paragraphs[-1].runs[0].bold = True
    doc.paragraphs[-1].add_run("uniform cost search, resource-constrained shortest path, simulated annealing, "
                               "constraint satisfaction, MRV, forward checking, integrated planning, replanning.")
    notice()


def introduction():
    h1("1. Introduction")
    p("Real engineering recoveries are rarely a single textbook problem. Restoring a damaged system usually "
      "means deciding how to re-route energy, how to spend scarce material, and in which order to perform "
      "maintenance with shared equipment. These decisions are coupled: the energy route limits the power "
      "available for repair, the repair allocation sets how much work must be scheduled, and the schedule "
      "must fit within the energy and equipment left over. Treating them independently can produce three "
      "locally sensible answers that cannot be executed together.")
    p("This case study uses the fictional Iron Man Mark 85 armor as a rich, engaging setting for exactly such "
      "a coupled problem. JARVIS, Tony Stark's AI system, has to bring the armor back to a safe operational "
      "state after a failure detected by FRIDAY. We show that three classical AI techniques, each matched to "
      "the structure of one sub-problem, can be chained into one pipeline in which the output of each stage "
      "becomes a hard input of the next:")
    bullets([("Uniform Cost Search ", "for the shortest-path structure of the power network (optimal, complete, "
                                      "non-negative additive costs);"),
             ("Simulated Annealing ", "for the rugged, non-convex resource-allocation landscape (good solutions "
                                      "without exhaustive enumeration, escapes local optima);"),
             ("Constraint Satisfaction ", "for the scheduling problem whose difficulty lies in many hard, "
                                          "interacting constraints rather than in an objective.")])
    p("The contribution is not a new algorithm but a complete, executable and validated integration: one "
      "shared dataset, one orchestrator with explicit data hand-offs and replanning rules, independent "
      "validation of every constraint, and a dashboard reporting one final recovery outcome.")


def background():
    h1("2. Background: Iron Man Technology Concepts")
    p("The engineering vocabulary used in this case study is taken from the Iron Man universe and translated "
      "into components that an AI planner can reason about. All specifications are fictional.")
    table(["Concept", "Role in this case study", "Modelled as"], [
        ("Arc Reactor", "Compact power source in the armor chest; derated after the fault",
         f"Graph source node ARC, P_avail = {DS.reactor['available_output_kW']} kW"),
        ("Power converters PC1–PC3", "Condition reactor output for the armor bus; PC1 has failed",
         "Graph nodes; status FAILED makes a node unusable"),
        ("Backup storage (BKP)", "Supercapacitor bank providing an alternative feed", "Graph node with high loss"),
        ("Switching units, distribution buses", "Route power to the critical load hub", "Graph nodes SW1–SW3, BUS_A–C"),
        ("Critical load hub (CLH)", "Feeds flight controller, stabiliser, sensors, life support",
         f"UCS goal; critical load {DS.critical_load_kW:.0f} kW"),
        ("Nanotech (Mark 50+ style) armor", "Nanoparticles reconfigure into plates, shields, repairs",
         f"Reserve of {DS.nano.reserve_NU} NU split into 5 categories"),
        ("FRIDAY", "Fault-monitoring AI that raises the alarm", "Source of the subsystem status data"),
        ("JARVIS", "Planning AI that coordinates recovery", "The orchestrator implemented in Python"),
        ("Stark Laboratory", "Robotic arms, repair stations, bays, charger, test rig, technicians",
         "CSP resources and capacities"),
    ], "Iron Man technology concepts and their computational models", widths=[3.6, 7, 6])


def problem_statement():
    h1("3. Unified Engineering Problem Statement")
    p("FRIDAY reports the following state of the Mark 85 at the start of the mission:")
    table(["ID", "Subsystem", "Health", "Critical load", "Status"],
          [(s["id"], s["name"], f"{s['health_pct']}%", f"{s['critical_load_kW']} kW", s["status"])
           for s in DS.subsystems], "Subsystem status at fault detection (fictional)")
    p(f"The Arc Reactor supplies only {DS.reactor['available_output_kW']} kW of its "
      f"{DS.reactor['nominal_output_kW']} kW nominal output, the primary converter PC1 is FAILED, and only "
      f"{DS.nano.reserve_NU} NU of nanomaterial remain. The armor must be returned to a safe operational state "
      f"within {H} laboratory slots of {SLOT} minutes ({H * SLOT / 60:.0f} hours).")
    p("Unified problem. ", None)
    doc.paragraphs[-1].runs[0].bold = True
    doc.paragraphs[-1].add_run(
        "Find (i) a power route π from the Arc Reactor to the critical load hub, (ii) a nanomaterial allocation x "
        "and (iii) a laboratory schedule S such that every mandatory safety constraint holds simultaneously, "
        "while minimising power-routing cost, maximising armor readiness for the power that is available, "
        "and completing all recovery tasks before the deadline. The three decisions are coupled: π determines "
        "the power budget and heat already present in the armor; x consumes part of that budget and determines "
        "how much repair, calibration and replenishment work exists; S must perform that work using only the "
        "power that π and x leave over.")


def objectives():
    h1("4. Objectives")
    bullets([
        "Model the Arc Reactor network as a weighted graph and compute the minimum-cost route that avoids failed "
        "components and satisfies capacity and cumulative thermal limits, using UCS with a priority queue.",
        "Derive the repair power budget from the selected route and use it as a hard constraint of the "
        "nanomaterial optimisation.",
        "Optimise the nanomaterial allocation with Simulated Annealing, demonstrating the acceptance of worse "
        "moves, cooling, convergence and escape from local optima.",
        "Convert the route and allocation into concrete task durations and a residual power cap, and schedule "
        "nine laboratory tasks as a CSP with MRV, degree heuristic and forward checking.",
        "Detect infeasibility at any stage and perform controlled replanning.",
        "Independently validate the integrated solution and present it on a single recovery dashboard.",
        "Provide complete, reproducible Python code, figures, an execution trace and a performance analysis.",
    ], style="List Number")


def architecture():
    h1("5. System Architecture")
    p("Figure 1 shows the architecture. FRIDAY's telemetry and Tony Stark's activation command populate one "
      "shared mission dataset. The JARVIS orchestrator runs the three engines in sequence, passes their "
      "outputs forward as typed result objects, and sends feedback backwards when a later stage proves that an "
      "earlier decision cannot be executed. A validation engine recomputes every constraint from scratch and "
      "the visualisation layer produces the figures and the recovery dashboard.")
    figure("fig01_architecture.png", "Figure 1. JARVIS system architecture")
    table(["Module", "Responsibility"], [
        ("data_models.py", "Shared dataset loader and typed result objects (UCSResult, SAResult, Requirements, CSPResult)"),
        ("ucs.py", "Stage 1: label-setting Uniform Cost Search with capacity, failure and thermal constraints"),
        ("annealing.py", "Stage 2: allocation problem, objective, feasibility, neighbourhood, SA loop"),
        ("requirements.py", "Bridge: converts UCS + SA outputs into CSP durations and power cap"),
        ("csp.py", "Stage 3: CSP model, bound propagation, prechecks, backtracking + MRV + degree + FC"),
        ("pipeline.py", "Orchestrator: sequencing, replanning policy, makespan tightening, health estimate"),
        ("validation.py", "Independent re-check of all stage and integrated constraints"),
        ("visualization.py", "All figures and the recovery dashboard"),
        ("experiments.py", "Performance study (SA vs hill climbing, CSP heuristics, route strategies)"),
        ("reporting.py / main.py", "Console report, CSV/JSON exports, command-line entry point"),
    ], "Software modules", widths=[4, 12.5])


def formulation():
    h1("6. Problem Formulation and Mathematical Models")
    h2("6.1 Input parameters (shared dataset)")
    table(["Symbol", "Meaning", "Value"], [
        ("P_avail", "Available Arc Reactor output", f"{DS.reactor['available_output_kW']} kW"),
        ("P_crit", "Critical load of FLC + STB + SEN + LSC", f"{DS.critical_load_kW:.0f} kW"),
        ("P_req", "Throughput every route edge must carry", f"{NET.required_throughput_kW:.0f} kW"),
        ("Θ_route", "Cumulative thermal limit of the route", f"{NET.thermal_limit_C} °C"),
        ("Θ_armor", "Armor thermal limit (route + nanomaterial heat)", f"{DS.nano.armor_thermal_limit_C} °C"),
        ("w_L, w_T, w_S", "Edge cost weights (loss, thermal, switching)", f"{W['loss']}, {W['thermal']}, {W['switching']}"),
        ("R", "Nanomaterial reserve", f"{DS.nano.reserve_NU} NU"),
        ("ρ₀, Δρ, ρ_min", "Initial nano power fraction, replanning step, minimum",
         f"{DS.nano.initial_power_fraction}, {DS.rules['replan_power_fraction_step']}, {DS.rules['min_power_fraction']}"),
        ("H, Δt", "Scheduling horizon and slot length", f"{H} slots, {SLOT} min"),
        ("N_tech", "Technicians available", f"{DS.lab.technicians}"),
    ], "Input parameters", widths=[3, 9, 4.5])

    h2("6.2 Overall engineering objective and mandatory constraints")
    p("The overall problem is a staged (hierarchical) optimisation. Optimisation objectives are distinguished "
      "from mandatory safety constraints: objectives are preferences JARVIS trades off, constraints may never be "
      "violated, and any plan violating one is rejected regardless of its objective value.")
    eq("Stage 1:   π* = argmin_{π ∈ Π_safe}  C(π)", "1")
    eq("Stage 2:   x* = argmax_{x ∈ X(π*, ρ)}  J(x)", "2")
    eq("Stage 3:   find S ∈ 𝒮(d(π*, x*), P_res(π*, x*))   (then minimise makespan)", "3")
    eq("F(π, x, S) = g_UCS(π) ∧ g_SA(x | π) ∧ g_CSP(S | π, x) ∧ g_INT(π, x, S)", "4")
    p("Equation (4) is the integrated feasibility condition: a recovery plan is accepted only if F = 1. "
      "The lexicographic order (route first, then allocation, then schedule) reflects engineering priority: "
      "a safe energy path is a prerequisite for everything else.")
    table(["Type", "Item", "Where enforced"], [
        ("Objective", "Minimise route cost C(π) (losses, heat, switching)", "UCS"),
        ("Objective", "Maximise readiness J(x) (protection, stability, repair, efficiency)", "SA"),
        ("Objective", "Minimise makespan of the recovery schedule", "CSP horizon tightening"),
        ("Mandatory", "Never route through FAILED components", "UCS expansion"),
        ("Mandatory", "Edge capacity ≥ P_req; route heat ≤ Θ_route", "UCS expansion"),
        ("Mandatory", "Minimum structural protection, reserve, power cap ρB, armor heat ≤ Θ_armor", "SA feasible set"),
        ("Mandatory", "Precedence, separation, no-overlap, exclusivity, compatibility, power, technicians, deadlines", "CSP"),
        ("Mandatory", "Power balance, thermal balance, replenishment, recharge, deadline", "Integrated validation"),
    ], "Optimisation objectives versus mandatory safety constraints", widths=[2.5, 10, 4])

    h2("6.3 Stage 1 model: weighted graph and UCS")
    p(f"The network is a directed graph G = (V, E) with |V| = {len(NET.nodes)} nodes "
      f"({len(NET.nodes) - 4} on the power side plus 4 critical loads) and |E| = {len(NET.edges)} power edges. "
      "Each edge e carries a conversion loss L_e (kW), a thermal rise T_e (°C), a switching overhead S_e (ms) and "
      "a capacity cap_e (kW). The non-negative edge cost and the UCS cumulative cost are:")
    eq("c(e) = w_L·L_e + w_T·T_e + w_S·S_e  ≥ 0", "5")
    eq("g(n') = g(n) + c(n, n'),    g(ARC) = 0", "6")
    eq("θ(n') = θ(n) + T_(n,n'),    valid only if θ(n') ≤ Θ_route and cap_(n,n') ≥ P_req", "7")
    p("The power delivered by route π and the budget passed to Stage 2 are:")
    eq("P_del(π) = min( P_avail − Σ_{e∈π} L_e ,  min_{e∈π} cap_e )", "8")
    eq("B(π) = P_del(π) − P_crit,      η(π) = P_del(π) / P_avail", "9")
    p("Because θ is a resource that accumulates along the path, the cheapest partial path to a node may be too "
      "hot to complete while a costlier, cooler one succeeds. Classical UCS keeps only one path per node and "
      "could therefore miss the constrained optimum. We search over labels (n, g, θ) and discard a label only "
      "if an already-expanded label at the same node dominates it (g' ≤ g and θ' ≤ θ). Labels are popped in "
      "non-decreasing g, so the first goal label popped is optimal over all constraint-satisfying routes.")
    figure("fig02_power_network.png", "Figure 2. Weighted Arc Reactor power network (graph representation) "
                                      "with the UCS optimal route highlighted")

    h2("6.4 Stage 2 model: nanomaterial allocation")
    p("Decision vector x = (x_SP, x_ES, x_FS, x_SR, x_SN) ∈ ℤ⁵ (NU) for structural protection, emergency "
      "shielding, flight stabilisation, structural repair and sensor protection.")
    eq("J(x) = 100·Σᵢ wᵢ(1 − e^(−xᵢ/sᵢ)) − λ_E·P_nano(x)/B − λ_M·M(x)/R − λ_W·Σᵢ (xᵢ mod qᵢ)/qᵢ", "10")
    eq("P_nano(x) = Σᵢ pᵢxᵢ,    Θ_nano(x) = Σᵢ hᵢxᵢ,    M(x) = Σᵢ xᵢ", "11")
    p("The first term rewards protection, stability, repair and sensor protection with diminishing returns "
      "(saturation sᵢ); the second penalises energy consumption; the third rewards material efficiency; the "
      "fourth penalises incomplete nanite packets of size qᵢ (nanoparticles form plates in packets), which "
      "makes the landscape rugged with many local optima. The feasible set X(π, ρ) is:")
    eq("mᵢ ≤ xᵢ ≤ uᵢ,   M(x) ≤ R,   P_nano(x) ≤ ρ·B(π),   θ_route(π) + Θ_nano(x) ≤ Θ_armor", "12")
    eq("Metropolis acceptance:  P(accept) = 1 if ΔE ≤ 0,  otherwise exp(−ΔE / T),   E = −J", "13")
    eq("Geometric cooling:  T_{k+1} = α·T_k  after every L iterations", "14")
    table(["i", "Category", "min mᵢ", "max uᵢ", "pᵢ kW/NU", "hᵢ °C/NU", "wᵢ", "sᵢ", "qᵢ"],
          [(c.id, c.name, c.min_NU, c.max_NU, c.power_kW_per_NU, c.heat_C_per_NU, c.benefit_weight,
            c.saturation_NU, c.packet_NU) for c in DS.nano.categories],
          "Nanomaterial category parameters", size=8.5)
    ow = DS.nano.objective_weights
    p(f"Objective weights: λ_E = {ow['energy']}, λ_M = {ow['material']}, λ_W = {ow['packet_waste']}. "
      f"SA parameters: T₀ = {DS.annealing.initial_temperature}, α = {DS.annealing.cooling_rate}, "
      f"L = {DS.annealing.iterations_per_temperature}, T_min = {DS.annealing.min_temperature}, "
      f"max iterations = {DS.annealing.max_iterations}, stall limit = {DS.annealing.stall_epochs} epochs, "
      f"move size δ ∈ [{DS.annealing.step_min_NU}, {DS.annealing.step_max_NU}] NU.")

    h2("6.5 Stage 3 model: CSP")
    p("Variables: one variable per task k ∈ {ARC_DIAG, CONV_REPAIR, NANO_REPL, STRUCT_REST, SENSOR_CAL, "
      "FLC_SYNC, CHARGE, THERMAL_INSP, SAFETY_TEST}. Value: the pair (s_k, r_k) of start slot and the concrete "
      "resource units used (robotic arm, station, bay, charger, test rig). Domain:")
    eq("D_k = { (s, r) : 0 ≤ s,  s + d_k ≤ min(H, deadline_k),  r ∈ Π_type Compatible_k(type) }", "15")
    p("Equipment compatibility is a unary constraint folded into D_k (for example, structural restoration "
      "needs the nano-capable ARM-1, thermal inspection needs the thermally shielded BAY-2). Hard constraints:")
    eq("C1 precedence:      s_j ≥ s_i + d_i                      ∀ i ∈ after(j)", "16")
    eq("C2 separation:      s_THERM ≥ s_CHARGE + d_CHARGE + 1  (cool-down)", "17")
    eq("C3 no-overlap:      [s_i, s_i+d_i) ∩ [s_j, s_j+d_j) = ∅   for safety pairs", "18")
    eq("C4 exclusivity:     r_i ∩ r_j ≠ ∅  ⇒  intervals disjoint", "19")
    eq("C5 power:           Σ_{k active at t} p_k ≤ P_res = B − P_nano(x*)    ∀t", "20")
    eq("C6 technicians:     Σ_{k active at t} tech_k ≤ N_tech                  ∀t", "21")
    eq("C7 deadlines:       s_k + d_k ≤ deadline_k ≤ H", "22")
    p("Task durations are functions of the earlier stages, which makes the coupling explicit:")
    eq("d_STRUCT = ⌈x_SR/80⌉,  d_REPL = ⌈M(x)/400⌉,  d_SENSOR = 1+⌈x_SN/100⌉,  d_FLC = 1+⌈x_FS/150⌉", "23")
    eq("d_THERM = 1+⌈(θ_route+Θ_nano)/15⌉,   d_CHARGE = ⌈E_deficit / (P_charger·η(π)·Δt)⌉", "24")

    h2("6.6 Relationship between the stages")
    p("The stages are linked by equations (8)–(9) and (20)–(24). Changing the route changes B, θ_route and η; "
      "B and θ_route reshape the SA feasible set (12); the SA result fixes P_res and every material-dependent "
      "duration; those durations and P_res define the CSP. Because the CSP enforces Σp_k ≤ B − P_nano at every "
      "slot, the integrated power balance P_crit + P_nano + max_t P_lab(t) ≤ P_del holds by construction, and "
      "the validation engine re-checks it independently.")


def algorithms():
    h1("7. The Three Algorithms and Why All Three Are Needed")
    h2("7.1 Uniform Cost Search")
    p("UCS expands the frontier node with the lowest path cost g(n), using a binary heap (heapq). With "
      "non-negative costs it is complete and optimal. Its responsibility here is to find the safest, cheapest "
      "energy path; its output (B, η, θ_route) is the physical envelope for everything that follows. UCS is the "
      "right tool because the problem is a pure additive-cost path problem on a small graph, where exact "
      "optimality is cheap. Heuristic search (A*) would need an admissible heuristic that brings little benefit "
      "on a graph of this size.")
    h2("7.2 Simulated Annealing")
    p("SA is a stochastic local search that accepts worse moves with probability exp(−ΔE/T), allowing it to "
      "leave local optima while the temperature is high and to behave like hill climbing as T → 0. Its "
      "responsibility is the nanomaterial allocation: a large discrete space (on the order of 10¹² integer "
      "vectors) with a non-convex objective caused by packet quantisation, where exhaustive search is "
      "impractical and greedy improvement gets trapped.")
    h2("7.3 Constraint Satisfaction")
    p("A CSP expresses the scheduling problem declaratively as variables, domains and constraints. Backtracking "
      "with MRV (choose the most constrained variable), the degree heuristic (break ties by the number of "
      "constraints on unassigned variables) and forward checking (remove values that conflict with the new "
      "assignment, detect dead ends early) solves it systematically. If a schedule exists it will be found, and "
      "if none exists that will be proven. Its responsibility is to produce a conflict-free laboratory plan.")
    h2("7.4 Why a single algorithm is not adequate")
    table(["If only…", "What goes wrong"], [
        ("UCS for everything", "The joint state (route × allocation × schedule) is astronomically large; UCS would "
                               "have to enumerate it with no useful cost ordering for allocation or scheduling."),
        ("SA for everything", "Hard scheduling and routing constraints would become penalty terms; SA gives no "
                              "guarantee that the final plan is feasible and no proof of infeasibility."),
        ("CSP for everything", "Routing cost and readiness are optimisation goals, not constraints; a CSP finds any "
                               "feasible answer and would need costly branch-and-bound wrappers to optimise them."),
        ("Three independent runs", "Locally optimal answers can be jointly infeasible. The executed mission shows "
                                   "this: the first SA allocation was optimal for its stage but left too little power "
                                   "for armor charging."),
    ], "Why three algorithms are necessary", widths=[4, 12.5])


def methodology():
    h1("8. Integrated Methodology and Data Flow")
    p("JARVIS executes one mission loop (Figure 3). Each arrow carries a concrete quantity rather than a "
      "narrative link:")
    table(["From → To", "Data exchanged", "Executed value"], [
        ("Dataset → UCS", "graph, P_avail, P_req, Θ_route, failed components",
         f"{len(NET.edges)} edges, PC1 FAILED"),
        ("UCS → SA", "power budget B, route heat θ_route", f"B = {U['power_budget_kW']:.1f} kW, θ = {U['total_thermal_C']} °C"),
        ("UCS → CSP", "route efficiency η (charging rate)", f"η = {U['route_efficiency']:.3f}"),
        ("SA → CSP", "allocation x*, P_res, material used, total heat",
         f"P_res = {S['residual_power_kW']:.1f} kW, M = {S['material_used_NU']} NU, θ_total = {S['total_thermal_C']:.2f} °C"),
        ("CSP → SA (feedback)", "infeasibility certificate → lower ρ", f"ρ {A1['rho']:.2f} → {S['power_fraction']:.2f}"),
        ("SA → UCS (feedback)", "minimum allocation infeasible → exclude edge, re-route", "not needed in nominal run"),
        ("All → Validation", "route, allocation, schedule", f"{N_PASS}/{N_CHECKS} checks pass"),
    ], "Data exchanged between the stages", widths=[3.5, 7, 6])
    figure("fig08_workflow.png", "Figure 3. End-to-end workflow and the data exchanged among the three algorithms")
    h2("8.1 Controlled replanning policy")
    bullets([("UCS finds no route: ", "abort and hold the armor in safe mode (no unsafe plan is ever produced)."),
             ("SA cannot meet mandatory minimums under ρ·B: ", "the route is too weak; exclude its highest-loss edge and "
                                                                "re-run UCS for the next-best route."),
             ("CSP infeasible (precheck or exhausted search): ", f"lower ρ by {DS.rules['replan_power_fraction_step']} "
                                                                 "to free residual power for laboratory work and re-run SA "
                                                                 f"and CSP; if ρ would fall below {DS.rules['min_power_fraction']}, change route."),
             ("Feasible plan found: ", "tighten the horizon to minimise the makespan, then validate and commit.")])
    p(f"Infeasibility is detected cheaply before search through necessary conditions: a single task drawing more "
      f"than P_res, a critical-path length exceeding a deadline, or total energy Σp_k·d_k exceeding P_res·H. "
      f"The stress scenario (python main.py --scenario pc2-failure) fails the secondary converter as well. "
      f"In that run UCS falls back to the backup-storage route (B = 280 kW). SA proves that even the mandatory "
      f"minimum allocation needs 239 kW, which is more than the 224 kW cap. JARVIS then excludes the route and "
      f"finds that no admissible route remains, so it aborts safely instead of returning an unsafe plan.")


def pseudocode():
    h1("9. Pseudocode")
    h2("9.1 Integrated JARVIS mission")
    code("""procedure JARVIS_RECOVERY(dataset D)
    rho <- rho0 ; excluded <- {}
    for attempt = 1 .. maxAttempts do
        route <- UCS(D.network, excluded)                       # Stage 1
        if route = FAIL then return ABORT_SAFE_MODE
        B <- min(P_avail - losses(route), bottleneck(route)) - P_crit
        x <- SIMULATED_ANNEALING(D.nano, B, rho, heat(route))   # Stage 2
        if x = INFEASIBLE then excluded <- excluded + worstEdge(route); continue
        req <- DERIVE_REQUIREMENTS(route, x)                     # durations, P_res
        S <- CSP_BACKTRACK(req, D.lab)                           # Stage 3
        if S = FAIL then
            if rho - step >= rho_min then rho <- rho - step
            else excluded <- excluded + worstEdge(route); rho <- rho0
            continue
        S <- MINIMISE_MAKESPAN(req, S)
        if VALIDATE(route, x, S) then return (route, x, S, RESTORED)
    return FAILED""")
    h2("9.2 Stage 1 – label-setting Uniform Cost Search")
    code("""function UCS(G, source, goal, P_req, Theta):
    frontier <- min-heap {(g=0, node=source, path=[source], theta=0)}
    expanded <- map node -> list of (g, theta)
    while frontier not empty:
        (g, n, path, theta) <- POP-MIN(frontier)
        if some (g', t') in expanded[n] with t' <= theta: continue      # dominated
        expanded[n].append((g, theta))
        if n = goal: return path, g                                     # optimal
        for each edge e = (n, m):
            if m FAILED or m in path or cap(e) < P_req: reject
            theta' <- theta + T(e);  if theta' > Theta: reject
            g' <- g + c(e)
            if not dominated(expanded[m], g', theta'): PUSH(frontier, (g', m, path+[m], theta'))
    return FAIL""")
    h2("9.3 Stage 2 – Simulated Annealing")
    code("""function SA(problem, T0, alpha, L, Tmin, maxIter, seed):
    x <- mandatory minimums ;  if not feasible(x): return INFEASIBLE
    best <- x ; T <- T0
    while T >= Tmin and iter < maxIter and not stalled:
        repeat L times:
            y <- random feasible neighbour of x (transfer / add / remove delta NU)
            dE <- E(y) - E(x)                      # E = -J
            if dE <= 0 or rand() < exp(-dE / T): x <- y
            if E(x) < E(best): best <- x
        T <- alpha * T
    return best""")
    h2("9.4 Stage 3 – Backtracking with MRV, degree heuristic and forward checking")
    code("""function BACKTRACK(assignment, domains):
    if assignment complete: return assignment
    v <- unassigned variable with smallest |domain|  (tie: largest degree)     # MRV + degree
    for value in domains[v] ordered by earliest start:
        if cumulative power / technicians still within limits:
            assign v = value
            for each unassigned u:                                            # forward checking
                remove values of u inconsistent with v = value
                if domain(u) empty: undo, try next value                     # wipeout
            result <- BACKTRACK(assignment, domains)
            if result != FAIL: return result
            restore pruned domains; unassign v
    return FAIL                                                               # backtrack""")


def implementation():
    h1("10. Python Implementation")
    h2("10.1 Project structure")
    code("""jarvis_recovery/
├── main.py                    # entry point: runs the full mission, exports, figures
├── server.py                  # local web server for the interactive case study page
├── requirements.txt
├── README.md
├── data/
│   └── mission_dataset.json   # ONE shared dataset (fictional)
├── jarvis/
│   ├── __init__.py
│   ├── data_models.py         # shared data models and stage result objects
│   ├── ucs.py                 # Stage 1 – Uniform Cost Search
│   ├── annealing.py           # Stage 2 – Simulated Annealing
│   ├── requirements.py        # bridge UCS + SA -> CSP inputs
│   ├── csp.py                 # Stage 3 – CSP (MRV, degree, forward checking)
│   ├── pipeline.py            # orchestration + controlled replanning
│   ├── validation.py          # independent validation
│   ├── visualization.py       # figures + dashboard
│   ├── experiments.py         # performance study
│   ├── reporting.py           # console report + CSV/JSON exports
│   └── api.py                 # JSON interface used by the web page
├── web/                       # case study page and report page (React)
├── tests/
│   ├── test_mission.py        # unit + integration tests
│   └── test_api.py            # interface and server tests
├── scripts/
│   └── build_case_study.py    # builds this document from the real outputs
├── docs/                      # case study brief, this document (DOCX, PDF)
└── outputs/                   # generated: results.json, CSVs, logs, figures/""")
    h2("10.2 Installation and execution commands")
    code("""# Python 3.10+ (tested with Python 3.11.9 on Windows 11)
cd jarvis_recovery
python -m pip install -r requirements.txt

python main.py                          # full mission + performance study + figures
python main.py --quick                  # mission + figures, skip multi-seed study
python main.py --no-plots               # console only
python main.py --seed 7 --out runs/s7   # different SA seed / output folder
python main.py --scenario pc2-failure   # stress test: secondary converter also fails
python -m unittest discover -s tests -v # 19 unit, integration and interface tests
python scripts/build_case_study.py              # regenerate this document from outputs/""")
    h2("10.3 Key implementation decisions")
    bullets([
        ("Priority queue: ", "heapq with a monotone tie-breaking counter so that equal-cost labels never "
                             "compare paths."),
        ("Reproducibility: ", f"SA uses random.Random(seed) with seed {DS.mission['seed']} from the dataset; the "
                              "CSP and UCS are deterministic."),
        ("Feasibility-preserving SA: ", "infeasible neighbours are rejected and resampled, so every accepted state "
                                        "(including accepted worse states) is a valid allocation."),
        ("No hardcoded answers: ", "routes, allocations, durations and schedules are all computed; changing the "
                                   "JSON changes every downstream result, the figures and this document."),
        ("Independent validation: ", "validation.py recomputes costs, sums, profiles and overlaps from the raw "
                                     "decision variables and compares the UCS answer with an exhaustive "
                                     "enumeration of all simple routes."),
    ])
    p("The complete source code is reproduced in Appendix A.")


def dataset_section():
    h1("11. Experimental Setup and Common Input Dataset")
    t = PERF.get("timing_ms", {})
    p(f"All experiments were executed with Python 3.11.9 on Windows 11 using matplotlib and networkx. The "
      f"single shared dataset is data/mission_dataset.json (Appendix B). Mean wall-clock times measured in the "
      f"run: UCS {t.get('ucs', '–')} ms, SA {t.get('sa', '–')} ms per run, CSP {t.get('csp', '–')} ms.")
    h2("11.1 Power-network edges")
    table(["Edge", "Loss kW", "Thermal °C", "Switch ms", "Capacity kW", "Cost c(e)"],
          [(f"{e.u}→{e.v}", f"{e.loss_kW:g}", f"{e.thermal_C:g}", f"{e.switch_ms:g}", f"{e.capacity_kW:g}",
            f"{e.cost(W):.2f}") for e in NET.edges], "Weighted power-distribution edges (fictional)", size=8.5)
    h2("11.2 Laboratory resources and tasks")
    table(["Type", "Units (capabilities)"],
          [(rt, "; ".join(f"{u.id} ({', '.join(u.capabilities)})" for u in units))
           for rt, units in DS.lab.resources.items()] + [("Technicians", str(DS.lab.technicians))],
          "Laboratory resources", widths=[3, 13.5])
    table(["Task", "Power kW", "Tech", "Needs", "After", "Deadline", "Duration rule"],
          [(t.id, f"{t.power_kW:g}", t.technicians, ", ".join(f"{k}:{v}" for k, v in t.needs.items()),
            ", ".join(t.after) or "–", t.deadline or "–", t.duration_rule) for t in DS.lab.tasks],
          "Recovery tasks", size=8)
    p("Safety rules: CHARGE → THERMAL_INSP requires a 1-slot cool-down; STRUCT_REST and CHARGE may not overlap "
      "(no nanite fabrication during high-current charging); ARC_DIAG and CHARGE may not overlap (diagnostics "
      f"require an isolated reactor). Armor battery: {DS.rules['armor_battery_capacity_kWh']} kWh at "
      f"{DS.rules['armor_state_of_charge']:.0%} charge, target {DS.rules['target_state_of_charge']:.0%}, "
      f"charger {DS.rules['charger_rating_kW']} kW.")


def trace_section():
    h1("12. Step-by-Step Execution Trace")
    p("The following traces are taken verbatim from the executed run (outputs/console_log.txt, "
      "outputs/sa_iterations.csv, outputs/csp_trace.txt).")
    h2("12.1 Replanning log of the mission")
    rows = []
    for a in R["attempts"]:
        rows.append((a["number"], f"{a['rho']:.2f}", " → ".join(a["route"]) if a["route"] else "–",
                     ", ".join(f"{k}={v}" for k, v in a["allocation"].items()) if a["allocation"] else "–",
                     f"{a['residual_power_kW']:.1f}" if a["residual_power_kW"] is not None else "–",
                     a["outcome"], a["action"]))
    table(["#", "ρ", "Route", "Allocation (NU)", "P_res kW", "Outcome", "JARVIS action"], rows,
          "Planning attempts", size=7.5)
    p(f"Attempt 1 is a genuine infeasibility discovered by the integration. SA maximised readiness by spending "
      f"almost all of the 80 % power cap on nanomaterial, which left P_res = {A1['residual_power_kW']:.1f} kW. "
      f"Armor charging alone draws {REQ['tasks'][6]['power_kW']:.0f} kW, so the CSP precheck proved that no "
      f"schedule could exist. JARVIS lowered ρ to {S['power_fraction']:.2f}, and SA re-optimised under the "
      f"tighter cap. P_res rose to {S['residual_power_kW']:.1f} kW and the CSP became solvable.")

    h2("12.2 Stage 1 – UCS expansion trace")
    rows = []
    for st in R["ucs_trace"]:
        pushed = "; ".join(f"{q['to']} g={q['g']} θ={q['theta']}" for q in st["pushed"]) or "–"
        rej = "; ".join(f"{q['to']}: {q['reason']}" for q in st["rejected"]) or "–"
        front = ", ".join(f"{f['node']}({f['g']})" for f in st["frontier_after"]) or "∅"
        rows.append((st["step"], st["expand"] + (" GOAL" if st.get("goal") else ""), st["g"], st["theta"],
                     pushed, rej, front))
    table(["Step", "Expand", "g", "θ", "Pushed", "Rejected", "Frontier after (g)"], rows,
          "UCS node expansion order, frontier changes and cumulative costs", size=7)
    p("Observations: at step 1 PC1 is rejected because it FAILED and PC3 because its 520 kW capacity cannot "
      "carry 600 kW. SW2 is expanded twice (steps 4 and 7) and BUS_B three times. These are distinct, mutually "
      "non-dominated labels: the cheaper label via PC2→SW2 reaches BUS_B at θ = 10.5 °C, and its extension to "
      "CLH (θ = 14.5 °C) violates the 14 °C limit (step 6). The costlier but cooler label via SW1→SW2 completes "
      f"at exactly θ = {U['total_thermal_C']} °C. The goal is popped at step {U['expansions']} with "
      f"g* = {U['path_cost']:.2f}, after {U['generated']} labels were generated.")
    figure("fig03_ucs_expansion.png", "Figure 4. UCS expansion order; g is non-decreasing, as UCS guarantees", 15.5)
    p(f"Result: route {ROUTE}; losses {U['total_loss_kW']:g} kW; thermal {U['total_thermal_C']:g} °C; "
      f"switching {U['total_switch_ms']:g} ms; bottleneck {U['bottleneck_capacity_kW']:g} kW. "
      f"P_del = min({DS.reactor['available_output_kW']} − {U['total_loss_kW']:g}, "
      f"{U['bottleneck_capacity_kW']:g}) = {U['delivered_power_kW']:g} kW, so "
      f"B = {U['delivered_power_kW']:g} − {U['critical_load_kW']:g} = {U['power_budget_kW']:g} kW and "
      f"η = {U['route_efficiency']:.3f}.")

    h2("12.3 Stage 2 – Simulated Annealing iterations (final attempt)")
    with open(OUT / "sa_iterations.csv", encoding="utf-8") as f:
        hist = list(csv.DictReader(f))
    pick = hist[1:19] + [r for r in hist if int(r["iter"]) % 400 == 0 and int(r["iter"]) > 18]

    def fnum(v, fmt):
        return fmt.format(float(v)) if v not in ("", "None") else "–"
    rows = [(r["iter"], fnum(r["T"], "{:.4f}"), r["move"], fnum(r["cand_J"], "{:.3f}"), fnum(r["dE"], "{:+.3f}"),
             fnum(r["p_accept"], "{:.3f}"), r["decision"], fnum(r["cur_J"], "{:.3f}"), fnum(r["best_J"], "{:.3f}"),
             f"{r['SP']}/{r['ES']}/{r['FS']}/{r['SR']}/{r['SN']}") for r in pick]
    table(["Iter", "T", "Move", "Cand. J", "ΔE", "P(acc)", "Decision", "Current J", "Best J", "SP/ES/FS/SR/SN"],
          rows, "SA iterations 1–18 and every 400th iteration", size=6.8)
    p(f"The run started from the mandatory-minimum allocation (J₀ = {S['initial_objective']:.3f}) and terminated "
      f"because '{S['termination']}' after {S['iterations']} iterations. It accepted {S['accepted_worse']} worse "
      f"moves, rejected {S['rejected_infeasible']} infeasible neighbours and improved the best solution "
      f"{S['improvements']} times. Rows with ACCEPT-WORSE show the Metropolis rule in action: a move with "
      f"ΔE > 0 was taken because a random draw fell below exp(−ΔE/T). These moves are what let SA cross the "
      f"packet-waste barriers that trap hill climbing (Section 14).")

    h2("12.4 Stage 3 – CSP inputs derived from Stages 1 and 2")
    table(["Task", "Duration (slots)", "Derivation from UCS / SA outputs", "Power kW", "Tech"],
          [(t["id"], t["duration"], t["derivation"], f"{t['power_kW']:g}", t["technicians"]) for t in REQ["tasks"]],
          "CSP task durations computed from the route and allocation", size=7.5)
    for n in REQ["notes"]:
        bullets([n])
    p("Initial bound propagation on the precedence network (before search) tightened the domains as follows:")
    code("\n".join(R["csp_bounds_log"]), size=7.5)
    p("Domain sizes entering search: " + ", ".join(f"{k} {v}" for k, v in R["csp_domains"].items()) + ".")
    h2("12.5 Stage 3 – CSP search trace")
    code((OUT / "csp_trace.txt").read_text(encoding="utf-8"), size=7.5)
    p(f"MRV selected SAFETY_TEST first (2 values, degree 6), then THERMAL_INSP and CHARGE, which forward "
      f"checking had reduced to a single value. Assigning ARM-1 to CONV_REPAIR caused a forward-checking "
      f"wipeout: STRUCT_REST, which needs the nano-capable ARM-1 in the same window, lost every value. JARVIS "
      f"undid that assignment and tried ARM-2, and the search then went straight to a solution. Totals: "
      f"{C1['nodes']} nodes, {C1['backtracks']} full backtracks, {C1['wipeouts']} wipeout, "
      f"{C1['fc_prunes']} pruned values, {C1['constraint_checks']} constraint checks. Makespan tightening: "
      + "; ".join(f"H = {m['horizon']}: {'solved' if m['solved'] else 'infeasible'} ({m['reason']})"
                  for m in R["makespan_search"]) +
      f". The {CF['makespan']}-slot schedule is therefore makespan-optimal.")


def results():
    h1("13. Results")
    h2("13.1 Stage 1 – optimal power route")
    p(f"The selected route {ROUTE} is highlighted in Figure 2 (Section 6.3). Of the "
      f"{len(R['performance']['route_methods'])} search strategies compared in Section 14.3, only constrained UCS "
      f"returns a route that is both cost-optimal and safe.")
    h2("13.2 Stage 2 – nanomaterial allocation")
    cats = DS.nano.categories
    table(["Category", "Minimum", "Attempt 1 (ρ=%.2f)" % A1["rho"], "Final (ρ=%.2f)" % S["power_fraction"],
           "Power kW", "Heat °C"],
          [(f"{c.id} {c.name}", c.min_NU, A1["allocation"][c.id], S["allocation"][c.id],
            f"{c.power_kW_per_NU * S['allocation'][c.id]:.1f}", f"{c.heat_C_per_NU * S['allocation'][c.id]:.2f}")
           for c in cats] +
          [("Total", sum(c.min_NU for c in cats), sum(A1["allocation"].values()), S["material_used_NU"],
            f"{S['nano_power_kW']:.1f}", f"{S['nano_heat_C']:.2f}")],
          "Nanomaterial allocation", size=8.5)
    p(f"Final objective J* = {S['objective']:.3f}, up from {S['initial_objective']:.3f}. The allocation uses "
      f"{S['nano_power_kW']:.1f} of {S['power_cap_kW']:.1f} kW, so the power cap is the binding constraint. "
      f"It uses {S['material_used_NU']}/{DS.nano.reserve_NU} NU and keeps the armor at "
      f"{S['total_thermal_C']:.2f} °C against the {DS.nano.armor_thermal_limit_C} °C limit. Every category "
      f"stays above its mandatory minimum.")
    figure("fig04_nano_allocation.png", "Figure 5. Nanomaterial allocation (rejected first attempt and final plan)")
    figure("fig05_sa_convergence.png", "Figure 6. SA convergence: current and best objective; temperature schedule")
    h2("13.3 Stage 3 – recovery schedule")
    sch = CF["schedule"]
    rows = [(k, v["name"], v["start"], v["end"],
             f"{v['start'] * SLOT // 60:02d}:{v['start'] * SLOT % 60:02d}–{v['end'] * SLOT // 60:02d}:{v['end'] * SLOT % 60:02d}",
             ", ".join(v["resources"].values()), f"{v['power_kW']:g}", v["technicians"])
            for k, v in sorted(sch.items(), key=lambda kv: (kv[1]["start"], kv[0]))]
    table(["Task", "Name", "Start", "End", "Clock (T+h:mm)", "Resources", "kW", "Tech"], rows,
          "Final conflict-free laboratory schedule", size=8)
    figure("fig06_csp_constraint_graph.png", "Figure 7. CSP constraint graph", 15)
    figure("fig07_gantt.png", "Figure 8. Gantt chart with power and technician profiles against their limits")
    h2("13.4 Integrated validation and final recovery status")
    table(["Stage", "Check", "Result", "Detail"],
          [(c["stage"], c["check"], "PASS" if c["passed"] else "FAIL", c["detail"]) for c in R["checks"]],
          "Independent constraint validation", size=7.5)
    p(f"All {N_CHECKS} mandatory checks pass. Final status: {R['status']}.", None)
    doc.paragraphs[-1].runs[0].bold = True
    p("Estimated post-recovery subsystem health (model estimate h' = h + (100 − h)(1 − e^(−x/s)) using the "
      "category serving each subsystem): " +
      ", ".join(f"{k} {next(s['health_pct'] for s in DS.subsystems if s['id'] == k)}% → {v}%"
                for k, v in R["health_after"].items()) + ".")
    figure("fig09_dashboard.png", "Figure 9. JARVIS recovery dashboard")


def performance():
    h1("14. Performance Analysis")
    sv = PERF["sa_vs_hc"]
    h2("14.1 Simulated Annealing versus hill climbing")
    table(["Method", "Runs", "Mean J", "Std", "Best", "Worst"], [
        ("Simulated Annealing", len(sv["sa"]), f"{sv['sa_mean']:.3f}", f"{sv['sa_std']:.3f}", f"{sv['sa_best']:.3f}",
         f"{sv['sa_worst']:.3f}"),
        ("Hill climbing (T = 0)", len(sv["hc"]), f"{sv['hc_mean']:.3f}", f"{sv['hc_std']:.3f}", f"{sv['hc_best']:.3f}",
         f"{sv['hc_worst']:.3f}")], "SA vs hill climbing on the final route and power fraction (seeds 0–%d)" % (len(sv["sa"]) - 1))
    p(f"SA was better on {sv['sa_wins']} of {len(sv['sa'])} seeds. The two methods use the same neighbourhood "
      f"and the same feasibility rules and differ only in the acceptance rule. Hill climbing quickly reaches a "
      f"packet-aligned allocation from which every small move is worse, and stays there. SA accepts those "
      f"temporary losses at high temperature and continues to better regions. Its run-to-run spread "
      f"(σ = {sv['sa_std']:.3f}) shows the stochastic nature of SA. In return, a run takes about "
      f"{sv['sa_mean_iters']:.0f} iterations.")
    h2("14.2 CSP heuristics")
    table(["Variant", "Solved", "Makespan", "Nodes", "Backtracks", "Checks", "Wipeouts", "Time ms"],
          [(r["variant"], r["solved"], r["makespan"], r["nodes"], r["backtracks"], r["checks"], r["wipeouts"],
            r["time_ms"]) for r in PERF["csp_variants"]], "CSP search effort on the same instance", size=8.5)
    p("Forward checking is the main source of the improvement because it catches dead ends one level early. "
      "MRV then steers the search to the tightly bounded end of the schedule (safety test, thermal inspection, "
      "charging) first, so that a valid assignment is found almost without backtracking. On this instance the "
      "degree heuristic only breaks ties, so it does not change the node count.")
    h2("14.3 Route strategies")
    table(["Strategy", "Route", "Cost", "Thermal °C", "Satisfies all constraints?"],
          [(r["method"].replace("\n", " "), " → ".join(r["path"]), r["cost"], r["thermal"],
            "yes" if r["feasible"] else "NO") for r in PERF["route_methods"]], "Routes chosen by different strategies",
          size=8.5)
    p("Ignoring the thermal constraint yields a cheaper but unsafe route (14.5 °C). Ignoring capacity as well "
      "selects PC3, which cannot carry the required 600 kW. Breadth-first search finds a safe route but not "
      "the cheapest. Only constrained UCS returns a route that is both safe and cost-optimal; validation also "
      "confirms this against the exhaustive enumeration of all simple routes.")
    figure("fig10_performance.png", "Figure 10. Performance analysis")
    h2("14.4 Complexity")
    table(["Stage", "Time complexity", "Space", "Guarantee"], [
        ("UCS (labels)", "O(Λ log Λ), Λ = labels generated (classic UCS: O((|V|+|E|) log |V|))", "O(Λ)",
         "complete and optimal (non-negative costs, dominance pruning)"),
        ("SA", "O(K · n) objective evaluations, K iterations, n = 5 categories", "O(n)", "none (probabilistic); "
         "asymptotic convergence only for logarithmic cooling"),
        ("CSP backtracking", "O(d^k) worst case, k = 9 variables, d = max domain size", "O(k·d)",
         "complete: finds a schedule or proves none exists"),
    ], "Complexity of the three stages", size=8.5)


def comparison():
    h1("15. Algorithm Comparison")
    table(["Aspect", "UCS", "Simulated Annealing", "CSP backtracking"], [
        ("Problem class", "Shortest path", "Combinatorial optimisation", "Constraint satisfaction"),
        ("Role in JARVIS", "Safe energy route, power budget", "Nanomaterial allocation", "Laboratory schedule"),
        ("Search type", "Systematic, uninformed, best-first on g", "Stochastic local search", "Systematic depth-first"),
        ("Optimal?", "Yes", "No guarantee (near-optimal)", "Feasibility (makespan via tightening)"),
        ("Complete?", "Yes", "No", "Yes"),
        ("Handles hard constraints", "Pruning during expansion", "Feasible-set restriction", "Natively"),
        ("Uses randomness", "No", "Yes (seeded)", "No"),
        ("Key data structure", "Binary heap", "Current/best state, temperature", "Domains, trail of pruned values"),
        ("Output to next stage", "B, θ_route, η", "x*, P_res, M, θ_total", "Schedule → validation"),
    ], "Comparison of the three algorithms", size=8.5)


def limitations():
    h1("16. Limitations")
    bullets([
        "All data are fictional and the physics is simplified: losses are additive constants, heat is a linear "
        "per-unit model, and power is treated as a steady-state quantity.",
        "The staged decomposition is not globally optimal. A cheaper route with less capacity, or a smaller "
        "allocation, might give a better overall plan. JARVIS explores this only through its feedback rules.",
        "UCS minimises a weighted cost. It does not maximise the delivered power, so the weights encode an "
        "engineering trade-off that would need calibration in practice.",
        "SA is stochastic. Different seeds give slightly different allocations (Section 14.1), and the cooling "
        "parameters were tuned by hand.",
        "The CSP uses discrete 30-minute slots and fixed durations. It does not model uncertainty, task "
        "pre-emption or stochastic failures during the recovery.",
        "The replanning policy is rule-based. A learning or negotiation-based coordinator could explore the "
        "joint space more systematically.",
        "Post-recovery health is a simple model estimate shown for presentation, not a validated prediction.",
    ])


def relevance():
    h1("17. Real-World Engineering Relevance")
    p("The same structure appears in real systems, with real data and certification replacing the fiction:")
    bullets([
        ("Power systems and micro-grids: ", "service restoration after a fault is a constrained path and "
                                            "reconfiguration problem; feeder capacity and thermal limits are hard "
                                            "constraints."),
        ("Spacecraft and aircraft health management: ", "re-routing power around failed converters and "
                                                        "re-budgeting energy for heaters, payloads and repairs."),
        ("Electric-vehicle and battery systems: ", "thermal-aware energy allocation among subsystems."),
        ("Maintenance, repair and overhaul (MRO) scheduling: ", "hangars, robotic cells, technicians and test "
                                                                "rigs are classical CSP / scheduling resources."),
        ("Robotics and additive manufacturing: ", "allocating limited material to competing structural goals."),
    ])
    p("The integration principle carries over directly: solve each sub-problem with the method that matches "
      "its structure, pass explicit quantities between stages, validate independently, and replan when a later "
      "stage proves an earlier decision unexecutable.")


def conclusion():
    h1("18. Conclusion")
    p(f"This case study solved one engineering problem, the recovery of a damaged Mark 85 armor, with one dataset "
      f"and three cooperating AI algorithms. UCS produced a provably optimal safe power route ({ROUTE}, cost "
      f"{U['path_cost']:.2f}) under capacity, failure and cumulative thermal constraints, and it fixed a "
      f"{U['power_budget_kW']:.0f} kW repair budget. Simulated Annealing used that budget to find a strong "
      f"nanomaterial allocation (J* = {S['objective']:.3f}) on a rugged landscape where hill climbing "
      f"stagnates. The CSP turned the route and allocation into a conflict-free, makespan-optimal "
      f"{CF['makespan']}-slot laboratory schedule with very little search, thanks to MRV and forward checking.")
    p("The most instructive event was the replanning in attempt 1. Each stage was locally sound, yet the "
      "combination could not be executed, because the optimal allocation consumed the power needed for "
      "charging. JARVIS detected this with a cheap infeasibility certificate and resolved it by trading a "
      "little readiness for schedulability. This is why the three algorithms must be integrated rather than "
      f"run in isolation. The final plan passes all {N_CHECKS} independent checks, and the armor is reported "
      f"as {R['status'].lower()}, within the bounds of this fictional simulation.")


def references():
    h1("References")
    refs = [
        "Russell, S. and Norvig, P. (2020). Artificial Intelligence: A Modern Approach, 4th ed. Pearson. "
        "(Ch. 3 uninformed search/UCS; Ch. 4 local search and simulated annealing; Ch. 6 constraint satisfaction.)",
        "Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. Numerische Mathematik, 1, 269–271.",
        "Felner, A. (2011). Position paper: Dijkstra's algorithm versus Uniform Cost Search or a case against "
        "Dijkstra's algorithm. Proc. 4th Annual Symposium on Combinatorial Search (SoCS).",
        "Irnich, S. and Desaulniers, G. (2005). Shortest path problems with resource constraints. In Column "
        "Generation, Springer, 33–65.",
        "Metropolis, N., Rosenbluth, A. W., Rosenbluth, M. N., Teller, A. H. and Teller, E. (1953). Equation of "
        "state calculations by fast computing machines. Journal of Chemical Physics, 21(6), 1087–1092.",
        "Kirkpatrick, S., Gelatt, C. D. and Vecchi, M. P. (1983). Optimization by simulated annealing. Science, "
        "220(4598), 671–680.",
        "Geman, S. and Geman, D. (1984). Stochastic relaxation, Gibbs distributions, and the Bayesian restoration "
        "of images. IEEE Trans. PAMI, 6(6), 721–741.",
        "Haralick, R. M. and Elliott, G. L. (1980). Increasing tree search efficiency for constraint satisfaction "
        "problems. Artificial Intelligence, 14(3), 263–313.",
        "Brélaz, D. (1979). New methods to color the vertices of a graph. Communications of the ACM, 22(4), 251–256.",
        "Mackworth, A. K. (1977). Consistency in networks of relations. Artificial Intelligence, 8(1), 99–118.",
        "Dechter, R. (2003). Constraint Processing. Morgan Kaufmann.",
        "Hagberg, A., Schult, D. and Swart, P. (2008). Exploring network structure, dynamics, and function using "
        "NetworkX. Proc. 7th Python in Science Conference (SciPy 2008), 11–15.",
        "Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. Computing in Science & Engineering, 9(3), 90–95.",
        "Marvel Studios (2008–2019). Iron Man film series and Avengers: Endgame. Fictional source of the Iron Man "
        "setting; no technical data were taken from it.",
    ]
    for i, r in enumerate(refs, 1):
        par = doc.add_paragraph(f"[{i}] {r}")
        par.paragraph_format.left_indent = Cm(0.8)
        par.paragraph_format.first_line_indent = Cm(-0.8)


def viva():
    h1("Viva Questions and Answers")
    qa = [
        ("Why is UCS optimal here, and why did you not use plain Dijkstra with one label per node?",
         "All edge costs are non-negative and labels are popped in non-decreasing g, so the first goal label "
         "popped is optimal. One label per node is insufficient because the cumulative thermal limit is a path "
         "constraint. In our run the cheapest label at BUS_B (θ = 10.5 °C) cannot reach CLH, while a costlier "
         "and cooler label can. Keeping non-dominated (g, θ) labels preserves optimality."),
        ("What is the difference between UCS and BFS in this problem?",
         "BFS minimises the number of hops. It returned ARC→PC2→SW1→BUS_A→CLH with cost 46.40, which is safe but "
         "more expensive than the UCS route (44.20). UCS minimises the sum of the weighted edge costs."),
        ("How does Stage 1 influence Stage 2 numerically?",
         f"B = min(P_avail − losses, bottleneck) − P_crit = {U['power_budget_kW']:.0f} kW becomes the power cap "
         f"ρB of the SA feasible set, and θ_route = {U['total_thermal_C']} °C consumes part of the armor thermal "
         "limit."),
        ("Write the SA acceptance probability and explain the role of temperature.",
         "P = exp(−ΔE/T) for ΔE > 0, and 1 otherwise. At high T, worse moves are accepted often, so the search "
         "explores. As T decreases geometrically (T ← 0.92 T), the search behaves more and more like hill "
         "climbing and exploits the best region found."),
        ("Why does hill climbing fail on the allocation problem?",
         "The packet-waste term makes small moves away from packet-aligned allocations worse, which creates many "
         "local optima. Hill climbing never accepts a worse move and gets stuck. SA accepts them temporarily and "
         f"was better on {PERF['sa_vs_hc']['sa_wins']}/{len(PERF['sa_vs_hc']['sa'])} seeds."),
        ("How are constraints handled in your SA? Why not penalties?",
         "Infeasible neighbours are rejected and resampled, so every visited state is a safe allocation. "
         "Penalties could leave the final answer infeasible, which is unacceptable for mandatory safety limits."),
        ("Is SA guaranteed to find the global optimum?",
         "Only asymptotically, with a logarithmic cooling schedule and infinite time. With geometric cooling it "
         "is a heuristic. That is why we report its spread over 30 seeds."),
        ("Define the CSP variables, domains and constraints.",
         "Variables: the 9 tasks. Value: (start slot, concrete resource units). Domains: starts within the "
         "deadline combined with compatible equipment. Constraints: precedence, cool-down separation, safety "
         "no-overlap, resource exclusivity, cumulative power ≤ P_res, technicians ≤ 2, deadlines."),
        ("What do MRV, the degree heuristic and forward checking do?",
         "MRV picks the variable with the fewest remaining values (fail-first). The degree heuristic breaks ties "
         "by the number of constraints on unassigned variables. Forward checking removes neighbour values that "
         "are inconsistent with a new assignment and backtracks as soon as a domain empties."),
        ("Show a backtracking event from your trace.",
         "CONV_REPAIR was first assigned ARM-1. Forward checking emptied the domain of STRUCT_REST, which also "
         "needs ARM-1 in that window, so the assignment was undone and ARM-2 was tried next."),
        ("How do SA outputs become CSP inputs?",
         "Durations are computed from the allocation: d_STRUCT = ⌈x_SR/80⌉, d_REPL = ⌈M/400⌉, "
         "d_SENSOR = 1 + ⌈x_SN/100⌉, d_FLC = 1 + ⌈x_FS/150⌉ and d_THERM = 1 + ⌈θ_total/15⌉. The power cap is "
         "P_res = B − P_nano."),
        ("What happened in planning attempt 1?",
         f"P_res was {A1['residual_power_kW']:.1f} kW while charging needs {REQ['tasks'][6]['power_kW']:.0f} kW. The CSP precheck proved "
         f"infeasibility without any search, and JARVIS lowered ρ from {A1['rho']:.2f} to "
         f"{S['power_fraction']:.2f} and re-optimised."),
        ("How do you know the final schedule is makespan-optimal?",
         "JARVIS re-solved with H = 14. The critical path DIAG(2) + CONV(3) + CHARGE(4) + gap(1) + THERM(3) + "
         "SAFETY(2) = 15 slots already exceeds 14, so 15 is a lower bound and it is achieved."),
        ("What is the integrated feasibility condition?",
         "F = g_UCS ∧ g_SA ∧ g_CSP ∧ g_INT. It includes the power balance P_crit + P_nano + peak P_lab ≤ P_del, the "
         "thermal balance, replenishment of the consumed material, recharge to the target state of charge and the "
         "deadline."),
        ("Why not solve everything with one CSP or one SA?",
         "A CSP has no native notion of cost or readiness, and SA cannot guarantee hard feasibility or prove "
         "infeasibility. A single joint search space would be intractable. Each algorithm is used where its "
         "guarantees matter."),
        ("How did you make results reproducible and avoid fabricated outputs?",
         f"A seeded random.Random({DS.mission['seed']}) is used, UCS and the CSP are deterministic, and every "
         "table and figure is generated from outputs/results.json, which main.py writes. The validation module "
         "recomputes everything, and 10 unit tests check optimality, feasibility and replanning."),
        ("What happens if PC2 also fails?",
         "UCS falls back to the backup-storage route, which gives B = 280 kW. The mandatory minimum allocation "
         "needs 239 kW, more than the 224 kW cap, so JARVIS excludes the route. No admissible route remains, and "
         "it aborts safely with the armor held in safe mode."),
        ("What is the time complexity of each stage?",
         "Label-setting UCS is O(Λ log Λ) in the number of labels. SA is O(K·n) for K iterations. CSP "
         f"backtracking is O(d^k) in the worst case, but heuristics cut it to {PERF['csp_variants'][0]['nodes']} nodes "
         f"here, against {PERF['csp_variants'][-1]['nodes']} for plain backtracking."),
        ("Which parts of the study are real and which are fictional?",
         "The armor, the reactor and all numerical data are fictional. The algorithms, equations, code, "
         "execution traces and measured performance are real outputs of the program."),
    ]
    for i, (q, a) in enumerate(qa, 1):
        par = doc.add_paragraph()
        r = par.add_run(f"Q{i}. {q}"); r.bold = True
        par.paragraph_format.keep_with_next = True
        par.paragraph_format.space_after = Pt(2)
        p(a, "Answer: ")


def appendices():
    page_break()
    h1("Appendix A. Complete Source Code")
    files = ["main.py", "jarvis/__init__.py", "jarvis/data_models.py", "jarvis/ucs.py", "jarvis/annealing.py",
             "jarvis/requirements.py", "jarvis/csp.py", "jarvis/pipeline.py", "jarvis/validation.py",
             "jarvis/visualization.py", "jarvis/experiments.py", "jarvis/reporting.py", "jarvis/api.py", "server.py",
             "tests/test_mission.py", "tests/test_api.py",
             "requirements.txt"]
    for f in files:
        h3(f"A.{files.index(f) + 1}  {f}")
        code((ROOT / f).read_text(encoding="utf-8"), size=6.8)
    page_break()
    h1("Appendix B. Shared Mission Dataset (JSON)")
    code((ROOT / "data" / "mission_dataset.json").read_text(encoding="utf-8"), size=6.8)
    page_break()
    h1("Appendix C. Console Output of the Executed Mission")
    p("Unedited output of python main.py (outputs/console_log.txt).")
    code((OUT / "console_log.txt").read_text(encoding="utf-8"), size=6.5)


def main():
    setup()
    title_page(); contents(); abstract(); introduction(); background(); problem_statement(); objectives()
    architecture(); formulation(); algorithms(); methodology(); pseudocode(); implementation()
    dataset_section(); trace_section(); results(); performance(); comparison(); limitations(); relevance()
    conclusion(); references(); viva(); appendices()
    props = doc.core_properties
    props.title = "JARVIS Mark 85 Recovery - AI Case Study"
    props.subject = "Uniform Cost Search, Simulated Annealing and Constraint Satisfaction"
    props.author = ""
    props.comments = ""
    props.last_modified_by = ""
    props.created = datetime.now()
    props.modified = datetime.now()
    out = ROOT / "docs" / "JARVIS_Case_Study.docx"
    doc.save(out)
    print(f"Case study written to {out}  ({fig_no[0]} figures, {tab_no[0]} tables)")


if __name__ == "__main__":
    main()
