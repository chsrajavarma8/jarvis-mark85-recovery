"use strict";

const { useState, useEffect } = React;
const html = htm.bind(React.createElement);
const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(+v) ? "–" : (+v).toFixed(d));

const NAV = [
  ["source", "Case study source"], ["approach", "Our approach"], ["checklist", "Checklist"],
  ["issues", "Issues solved"], ["measurements", "Measurements"],
];

const DONE = "Done", PART = "Partial", NOT = "Not done";

const CHECKLIST = [
  {
    task: "Task 3 · Uniform Cost Search: Minimum-Loss Arc-Reactor Power Distribution",
    rows: [
      ["Task", "Weighted graph with Arc Reactor, converters, storage buffer, buses and subsystem loads", DONE, "data/mission_dataset.json: ARC, PC1–PC3, BKP, SW1–SW3, BUS_A–BUS_C, CLH and four loads"],
      ["Task", "Non-negative edge cost from conversion loss, thermal burden and switching overhead", DONE, "Edge.cost in jarvis/data_models.py: c(e) = 1.0·loss + 0.5·heat + 0.4·switching"],
      ["Task", "UCS finds the minimum-cost path from the Arc Reactor to the critical subsystem", DONE, "jarvis/ucs.py, goal = Critical Load Hub that feeds FLC, STB, SEN and LSC"],
      ["Challenge", "Distinguish electrical topology from path cost", DONE, "Fewest-hop BFS route costs 46.40 against 44.20 for UCS (performance study)"],
      ["Challenge", "Enforce converter capacity and thermal limits", DONE, "Every edge ≥ 600 kW, cumulative heat ≤ 14 °C, label dominance keeps cooler routes alive"],
      ["Challenge", "Report cumulative cost", DONE, "Path cost g*, losses, heat and switching reported on the home page and in validation"],
      ["Challenge", "Explain why UCS fits when no heuristic is available", DONE, "Home page method box and the case study document"],
      ["Extension", "Multi-load version with a reserve; compare independent paths with a shared bus", PART, "All loads share one hub route and the budget B keeps the reserve for SA; independent per-load paths are not compared"],
    ],
  },
  {
    task: "Task 7 · Simulated Annealing: Finite Nanomaterial Allocation",
    rows: [
      ["Task", "State = allocation of the nanomaterial reserve across technical functions", DONE, "Five functions SP, ES, FS, SR, SN in nano-units (share of 1200 NU)"],
      ["Task", "Objective with protection, maneuverability, structure, sensing, energy and remaining reserve", DONE, "jarvis/annealing.py: benefit terms − energy − material − packet-waste penalties"],
      ["Task", "Always accept improvements, accept worse moves with P = exp(−Δ/T)", DONE, "Metropolis rule with geometric cooling T ← 0.92·T"],
      ["Challenge", "Allocations must sum to the available nanomaterial", PART, "Total is kept ≤ reserve; unused material stays as reserve and is part of the objective"],
      ["Challenge", "Minimum structural / life-support coverage preserved", DONE, "Per-function minimums, structural protection ≥ 300 NU"],
      ["Challenge", "Power and thermal limits never exceeded", DONE, "Nano power ≤ ρ·B and route heat + nano heat ≤ 30 °C, infeasible neighbours rejected"],
      ["Challenge", "Show how accepting a worse state escapes a local optimum", DONE, "Uphill moves are counted; SA beats hill climbing in every seed of the 30-seed study"],
      ["Extension", "Compare different cooling schedules", NOT, "Only the geometric schedule is used"],
      ["Extension", "Reduce the nanomaterial and re-optimize", NOT, "Reserve is fixed at 1200 NU"],
    ],
  },
  {
    task: "Task 11 · CSP: Stark Lab Fabrication, Charging and Integration Scheduling",
    rows: [
      ["Task", "Variables are engineering activities", PART, "Nine activities (diagnostics, converter repair, restoration, replenishment, calibration, flight sync, charging, thermal inspection, safety test); Veronica, satellite, EDITH and B.A.R.F. activities are not modelled"],
      ["Task", "Domains are time slots and resources", DONE, "Value = (start slot, equipment units); compatibility handled in the domain"],
      ["Task", "Precedence, exclusivity, compatibility, power, safety separation, deadlines", DONE, "Constraints C1–C7 in jarvis/csp.py"],
      ["Task", "Backtracking with MRV, degree heuristic and forward checking", DONE, "All three are used and can be switched off for the heuristic study"],
      ["Challenge", "Distinguish hard constraints from preferences", PART, "All constraints are hard; the shortest makespan is the only optimisation goal"],
      ["Challenge", "Point to the conflicting constraint instead of only 'no solution'", DONE, "Prechecks name the conflict, e.g. CHARGE draws 120 kW > P_res 111.9 kW"],
      ["Extension", "Urgent armor repair while all bays are occupied; re-solve", NOT, "Not implemented"],
    ],
  },
  {
    task: "Integration (beyond the brief)",
    rows: [
      ["Added", "UCS output feeds SA, SA output feeds CSP", DONE, "B = delivered − critical load → SA; P_res = B − P_nano and task durations → CSP"],
      ["Added", "Controlled replanning when a stage is infeasible", DONE, "jarvis/pipeline.py lowers ρ or excludes the weakest edge"],
      ["Added", "Independent validation of every result", DONE, "36 checks in jarvis/validation.py"],
      ["Added", "Stress scenario with a second converter failure", DONE, "PC1 + PC2 failed → safe abort, armor held in safe mode"],
    ],
  },
];

const SUBMISSION = [
  ["Engineering problem statement", DONE, "Home page section 1, case study document"],
  ["Stark technologies involved", DONE, "Arc Reactor network, nanotech reserve, lab equipment"],
  ["State / solution representation", DONE, "Route labels, allocation vector, (start, units) assignments"],
  ["Algorithm procedure", DONE, "jarvis/ucs.py, jarvis/annealing.py, jarvis/csp.py"],
  ["Cost / fitness / constraint definitions", DONE, "Edge cost, objective J(x), constraints C1–C7"],
  ["Pseudocode or program", DONE, "Python package jarvis/ and the case study document"],
  ["Sample technical input", DONE, "data/mission_dataset.json"],
  ["Step-by-step trace", DONE, "outputs/console_log.txt, outputs/csp_trace.txt, outputs/sa_iterations.csv"],
  ["Sample output", DONE, "outputs/results.json, outputs/schedule.csv"],
  ["Why the algorithm fits", DONE, "Home page method boxes, case study document"],
  ["Limitations / failure cases", DONE, "Case study document and the checklist above"],
  ["Technical diagram", DONE, "outputs/figures/fig01–fig10 and the live charts on the home page"],
];

const ISSUES = [
  ["Schedule infeasible at the first power split", "With ρ = 0.80 the lab gets P_res = 111.9 kW but armor charging needs 120 kW.",
    "The replanner lowers ρ to 0.70, which frees P_res = 160 kW; the CSP then solves.", "2 planning attempts, final P_res 160 kW"],
  ["Thermal limit is a path constraint", "A plain closed set lets a cheap but hot partial route block a cooler one that is still feasible.",
    "UCS keeps several labels per node and discards a label only when another is both cheaper and cooler.", "Optimal route 44.20 confirmed by exhaustive check of all 13 routes"],
  ["Second converter failure", "With PC1 and PC2 down the only route is through backup storage, B = 280 kW.",
    "SA detects that the mandatory minimums need 239 kW > ρ·B; JARVIS aborts safely instead of committing an unsafe plan.", "Stress scenario test passes"],
  ["Shortest schedule not guaranteed by the first solution", "Backtracking returns the first consistent schedule, not the shortest one.",
    "The horizon is tightened to makespan − 1 until the CSP becomes infeasible.", "15 slots solved, 14 slots proven infeasible"],
  ["CSP run on its own failed by default", "Stand-alone scheduling used ρ = 0.80 without replanning.",
    "When ρ is left blank, CSP mode steps ρ down like the replanner.", "Auto-selected ρ = 0.70"],
  ["Results must not trust the solvers", "A solver bug could report a plan that breaks a rule.",
    "Validation recomputes every quantity from the dataset and the decision variables.", "36 / 36 checks pass"],
  ["Browser rejected some results", "A missing route has infinite cost, which is not valid JSON.",
    "Non-finite numbers are converted to null before sending.", "API tests use strict JSON"],
  ["Scripts did not load on Windows", "The Windows registry can map .js to text/plain.",
    "The server sends text/javascript explicitly.", "Page loads offline from web/vendor"],
];

function App() {
  const [md, setMd] = useState(null);
  const [perf, setPerf] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    fetch("docs/case_study_source.md").then((r) => r.text()).then(setMd).catch((e) => setErr(e.message));
    fetch("api/performance").then((r) => r.json()).then(setPerf).catch((e) => setErr(e.message));
  }, []);
  return html`
    <${Header} />
    <main className="page">
      <section className="hero">
        <h1>Case Study Report</h1>
        <p>The college case study brief, the problem we chose to solve, how we approached it, a point-by-point check of the brief, the issues we met and the measurements of the final system.</p>
      </section>
      ${err ? html`<div className="msg err">${err}</div>` : null}
      <${Source} md=${md} />
      <${Approach} />
      <${Checklist} />
      <${Issues} />
      <${Measurements} p=${perf} />
    </main>
    <${Footer} />`;
}

function Header() {
  const [active, setActive] = useState(null);
  useEffect(() => {
    const obs = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)), { rootMargin: "-40% 0px -55% 0px" });
    NAV.forEach(([id]) => { const el = document.getElementById(id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, []);
  return html`<header className="header" id="top"><div className="header-in">
    <div className="logo"><span>JARVIS</span> Mark 85 Recovery</div>
    <nav className="nav">${NAV.map(([id, label]) => html`<a key=${id} href=${"#" + id} className=${active === id ? "active" : ""}>${label}</a>`)}</nav>
    <a className="badge back" href="index.html">← Home</a>
  </div></header>`;
}

function Section({ id, title, lead, children }) {
  return html`<section id=${id} className="section"><h2>${title}</h2>${lead ? html`<p className="lead">${lead}</p>` : null}${children}</section>`;
}

function Tag({ s }) {
  const cls = s === DONE ? "ok" : s === PART ? "warn" : "no";
  return html`<span className=${"tag " + cls}>${s}</span>`;
}

function Source({ md }) {
  return html`<${Section} id="source" title="1. Case study source" lead="The full brief issued by the college, reproduced without changes.">
    <div className="card prose">${md ? html`<div dangerouslySetInnerHTML=${{ __html: renderMarkdown(md) }} />` : html`<p className="muted">Loading…</p>`}</div>
  <//>`;
}

function Approach() {
  return html`<${Section} id="approach" title="2. Our problem statement and approach">
    <div className="grid2">
      <div className="card"><h3>Problem statement</h3>
        <p>FRIDAY reports a fault in the Mark 85: primary converter PC1 has failed, the Arc Reactor is derated to 1000 kW, only 1200 NU of nanomaterial remain and five subsystems are damaged. JARVIS must restore the armor safely within an 8-hour laboratory window.</p>
        <p>From the twelve tasks in the brief we solve <b>Task 3 (UCS)</b>, <b>Task 7 (Simulated Annealing)</b> and <b>Task 11 (CSP)</b>, and connect them into one recovery mission instead of three separate exercises.</p></div>
      <div className="card"><h3>Approach</h3>
        <ol className="steps">
          <li><b>UCS</b> finds the cheapest safe power route and fixes the power budget B.</li>
          <li><b>Simulated Annealing</b> shares the nanomaterial under ρ·B, which fixes the lab power P_res and the repair workload.</li>
          <li><b>CSP</b> schedules nine lab tasks whose durations come from steps 1 and 2.</li>
          <li><b>Replanning</b>: if a later stage is infeasible, an earlier decision is changed and the mission is re-run.</li>
          <li><b>Validation</b>: every constraint is recomputed independently before the plan is accepted.</li>
        </ol></div>
    </div>
    <div className="card"><h3>How it was built</h3>
      <table><tbody>
        <tr><td className="muted">Data</td><td>One shared dataset (data/mission_dataset.json) read by every stage</td></tr>
        <tr><td className="muted">Solvers</td><td>Python 3.11 package jarvis/: ucs.py, annealing.py, csp.py, requirements.py, pipeline.py, validation.py</td></tr>
        <tr><td className="muted">Experiments</td><td>SA against hill climbing over 30 seeds, five CSP heuristic combinations, four routing strategies</td></tr>
        <tr><td className="muted">Interface</td><td>React page served by a standard-library Python server (server.py), no build step</td></tr>
        <tr><td className="muted">Testing</td><td>19 unit, integration, API and server tests (python -m unittest discover -s tests)</td></tr>
      </tbody></table></div>
  <//>`;
}

function Checklist() {
  const all = CHECKLIST.flatMap((g) => g.rows);
  const count = (s) => all.filter((r) => r[2] === s).length;
  return html`<${Section} id="checklist" title="3. Verification checklist" lead="Every point of the three chosen tasks, checked against the code and the measured results.">
    <div className="stats">
      <div className="stat good"><div className="k">Done</div><div className="v">${count(DONE)}</div></div>
      <div className="stat"><div className="k">Partial</div><div className="v" style=${{ color: "var(--amber)" }}>${count(PART)}</div></div>
      <div className="stat bad"><div className="k">Not done</div><div className="v">${count(NOT)}</div></div>
      <div className="stat"><div className="k">Tasks of the brief solved</div><div className="v">3<small>/ 12</small></div><div className="d">Tasks 3, 7 and 11</div></div>
    </div>
    ${CHECKLIST.map((g) => html`<div key=${g.task} className="card"><h3>${g.task}</h3>
      <div className="tbl"><table><thead><tr><th style=${{ width: "100px" }}>Point</th><th>Requirement</th><th style=${{ width: "100px" }}>Status</th><th>Evidence</th></tr></thead>
      <tbody>${g.rows.map((r, i) => html`<tr key=${i}><td className="muted">${r[0]}</td><td>${r[1]}</td><td><${Tag} s=${r[2]} /></td><td className="muted">${r[3]}</td></tr>`)}</tbody></table></div></div>`)}
    <div className="card"><h3>Suggested submission format (section 8 of the brief)</h3>
      <div className="tbl"><table><thead><tr><th>#</th><th>Item</th><th>Status</th><th>Where</th></tr></thead>
      <tbody>${SUBMISSION.map((r, i) => html`<tr key=${i}><td className="num">${i + 1}</td><td>${r[0]}</td><td><${Tag} s=${r[1]} /></td><td className="muted">${r[2]}</td></tr>`)}</tbody></table></div></div>
  <//>`;
}

function Issues() {
  return html`<${Section} id="issues" title="4. Issues found and how they were solved">
    <div className="card"><div className="tbl"><table>
      <thead><tr><th>Issue</th><th>Cause</th><th>Solution</th><th>Result</th></tr></thead>
      <tbody>${ISSUES.map((r, i) => html`<tr key=${i}><td><b>${r[0]}</b></td><td className="muted">${r[1]}</td><td>${r[2]}</td><td className="mono">${r[3]}</td></tr>`)}</tbody>
    </table></div></div>
  <//>`;
}

function Measurements({ p }) {
  if (!p) return html`<${Section} id="measurements" title="5. Measurements"><div className="card empty">Running the mission and the performance study…</div><//>`;
  const u = p.ucs, s = p.sa, c = p.csp, pf = p.performance, sv = pf.sa_vs_hc;
  return html`<${Section} id="measurements" title="5. Measurements" lead="Measured live on this machine when the page was opened (reference seed 85).">
    <div className="stats">
      <div className="stat blue"><div className="k">Route cost</div><div className="v">${fmt(u.cost, 2)}</div><div className="d">${u.path.join(" → ")}</div></div>
      <div className="stat blue"><div className="k">Readiness J*</div><div className="v">${fmt(s.objective, 3)}</div><div className="d">from ${fmt(s.initial_objective, 3)}</div></div>
      <div className="stat blue"><div className="k">Makespan</div><div className="v">${c.makespan}<small>slots</small></div><div className="d">${fmt(c.makespan * c.slot_minutes / 60)} h of ${fmt(c.horizon * c.slot_minutes / 60)} h</div></div>
      <div className="stat good"><div className="k">Validation</div><div className="v">${p.checks_passed}/${p.checks_total}</div><div className="d">checks passed</div></div>
      <div className="stat"><div className="k">Full mission time</div><div className="v">${fmt(p.mission_ms, 0)}<small>ms</small></div><div className="d">${p.attempts.length} planning attempts</div></div>
    </div>
    <div className="grid3" style=${{ marginTop: "14px" }}>
      <div className="card"><h3>UCS</h3><table><tbody>
        <tr><td className="muted">Losses / heat / switching</td><td>${fmt(u.loss_kW, 0)} kW · ${fmt(u.thermal_C)} °C · ${fmt(u.switch_ms, 0)} ms</td></tr>
        <tr><td className="muted">Delivered power</td><td>${fmt(u.delivered_kW, 0)} kW</td></tr>
        <tr><td className="muted">Budget B</td><td>${fmt(u.budget_kW, 0)} kW</td></tr>
        <tr><td className="muted">Route efficiency</td><td>${fmt(u.efficiency, 3)}</td></tr>
        <tr><td className="muted">Labels expanded / generated / pruned</td><td>${u.expansions} / ${u.generated} / ${u.pruned}</td></tr>
        <tr><td className="muted">Time per search</td><td>${fmt(pf.timing_ms.ucs, 3)} ms</td></tr>
      </tbody></table></div>
      <div className="card"><h3>Simulated Annealing</h3><table><tbody>
        <tr><td className="muted">Allocation (NU)</td><td>${Object.entries(s.allocation).map(([k, v]) => `${k} ${v}`).join(" · ")}</td></tr>
        <tr><td className="muted">Material</td><td>${s.material_NU} / 1200 NU</td></tr>
        <tr><td className="muted">Nano power / cap</td><td>${fmt(s.nano_power_kW)} / ${fmt(s.power_cap_kW)} kW (ρ = ${fmt(s.rho, 2)})</td></tr>
        <tr><td className="muted">Lab power P_res</td><td>${fmt(s.residual_kW)} kW</td></tr>
        <tr><td className="muted">Iterations / improvements / uphill</td><td>${s.iterations} / ${s.improvements} / ${s.accepted_worse}</td></tr>
        <tr><td className="muted">Time per run</td><td>${fmt(pf.timing_ms.sa, 1)} ms</td></tr>
      </tbody></table></div>
      <div className="card"><h3>CSP</h3><table><tbody>
        <tr><td className="muted">Search nodes / backtracks</td><td>${c.nodes} / ${c.backtracks}</td></tr>
        <tr><td className="muted">Constraint checks / FC prunes</td><td>${c.checks} / ${c.prunes}</td></tr>
        <tr><td className="muted">Makespan proof</td><td>${c.makespan_search.map((x) => `H=${x.horizon} ${x.solved ? "solved" : "infeasible"}`).join(", ")}</td></tr>
        <tr><td className="muted">Time per solve</td><td>${fmt(pf.timing_ms.csp, 2)} ms</td></tr>
      </tbody></table></div>
    </div>
    <div className="grid3" style=${{ marginTop: "14px" }}>
      <div className="card"><h3>SA against hill climbing <small>${sv.sa.length} seeds</small></h3><table>
        <thead><tr><th></th><th className="num">Mean J</th><th className="num">Std</th><th className="num">Best</th><th className="num">Worst</th></tr></thead><tbody>
        <tr><td>Simulated Annealing</td><td className="num">${fmt(sv.sa_mean, 3)}</td><td className="num">${fmt(sv.sa_std, 3)}</td><td className="num">${fmt(sv.sa_best, 3)}</td><td className="num">${fmt(sv.sa_worst, 3)}</td></tr>
        <tr><td>Hill climbing</td><td className="num">${fmt(sv.hc_mean, 3)}</td><td className="num">${fmt(sv.hc_std, 3)}</td><td className="num">${fmt(sv.hc_best, 3)}</td><td className="num">${fmt(sv.hc_worst, 3)}</td></tr>
      </tbody></table><p className="muted" style=${{ marginTop: "10px", fontSize: "13.5px" }}>SA is better in ${sv.sa_wins} of ${sv.sa.length} seeds.</p></div>
      <div className="card"><h3>CSP heuristics</h3><table>
        <thead><tr><th>Variant</th><th className="num">Nodes</th><th className="num">Backtracks</th><th className="num">ms</th></tr></thead>
        <tbody>${pf.csp_variants.map((r) => html`<tr key=${r.variant}><td>${r.variant}</td><td className="num">${r.nodes}</td><td className="num">${r.backtracks}</td><td className="num">${fmt(r.time_ms, 2)}</td></tr>`)}</tbody></table></div>
      <div className="card"><h3>Routing strategies</h3><table>
        <thead><tr><th>Strategy</th><th className="num">Cost</th><th className="num">Heat</th><th>Safe</th></tr></thead>
        <tbody>${pf.route_methods.map((r) => html`<tr key=${r.method}><td>${r.method}</td><td className="num">${fmt(r.cost, 2)}</td><td className="num">${fmt(r.thermal)}</td><td>${r.feasible ? html`<span className="tag ok">yes</span>` : html`<span className="tag no">no</span>`}</td></tr>`)}</tbody></table></div>
    </div>
  <//>`;
}

function Footer() {
  return html`<footer className="site-footer"><div className="footer-in">
    <div className="footer-bottom" style=${{ marginTop: 0, borderTop: "none", paddingTop: 0 }}>
      <span>Fictional engineering simulation for an academic AI case study. Mark 85, Arc Reactor, FRIDAY and JARVIS are fictional (Marvel).</span>
      <span><a href="index.html">Home</a> · <a href="#top">Back to top ↑</a></span>
    </div>
  </div></footer>`;
}

function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function inline(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>"); }

function renderMarkdown(md) {
  const lines = md.replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    let m;
    if ((m = l.match(/^(#{1,3}) (.*)$/))) { const n = m[1].length + 1; out.push(`<h${n}>${inline(m[2])}</h${n}>`); i++; continue; }
    if (l.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) { rows.push(lines[i]); i++; }
      const cells = (r) => r.slice(1, -1).split("|").map((c) => c.trim());
      const head = cells(rows[0]);
      out.push(`<div class="tbl"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows.slice(2).map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
      continue;
    }
    if (l.startsWith("- ")) {
      const items = [];
      while (i < lines.length && lines[i].startsWith("- ")) { items.push(lines[i].slice(2)); i++; }
      out.push(`<ul>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ul>`);
      continue;
    }
    if (l.startsWith("> ")) { out.push(`<blockquote>${inline(l.slice(2))}</blockquote>`); i++; continue; }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#|\||- |> )/.test(lines[i])) { para.push(lines[i]); i++; }
    out.push(`<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
