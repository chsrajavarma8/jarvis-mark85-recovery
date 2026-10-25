"use strict";

const { useState, useEffect, useRef } = React;
const html = htm.bind(React.createElement);

const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(+v) ? "–" : (+v).toFixed(d));
const BLUE = "#2563eb", GRAY = "#9ca3af", LINE = "#e5e7eb", TEXT = "#1f2937", MUTED = "#6b7280",
  RED = "#dc2626", GREEN = "#16a34a", AMBER = "#d97706";

const SECTIONS = [
  ["problem", "Problem"], ["integration", "Integration"], ["validation", "Validation"], ["conclusion", "Conclusion"],
];
const MODE_TARGET = { integrated: "conclusion", ucs: "ucs", sa: "sa", csp: "csp" };
const MODE_NAME = { integrated: "Full mission", ucs: "UCS run", sa: "SA run", csp: "CSP run" };

function App() {
  const [info, setInfo] = useState(null);
  const [failed, setFailed] = useState(new Set(["PC1"]));
  const [settings, setSettings] = useState({ available_kW: "", seed: "", rho: "" });
  const [res, setRes] = useState({});
  const [busy, setBusy] = useState(null);
  const [last, setLast] = useState(null);
  const [scrollTo, setScrollTo] = useState(null);
  const [ranWith, setRanWith] = useState(null);

  useEffect(() => {
    fetch("api/dataset").then((r) => r.json()).then((d) => {
      setInfo(d);
      setFailed(new Set(d.defaults.mission.failed_nodes));
      const st = { available_kW: d.defaults.mission.available_kW, seed: d.defaults.mission.seed, rho: "" };
      setSettings(st);
      run("integrated", { failedSet: new Set(d.defaults.mission.failed_nodes), settings: st, quiet: true });
    }).catch((e) => setLast({ ok: false, error: "Cannot reach the server: " + e.message }));
  }, []);

  useEffect(() => {
    if (!scrollTo) return;
    const el = document.getElementById(scrollTo);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    setScrollTo(null);
  }, [scrollTo, res]);

  async function run(mode, opts = {}) {
    const fs = opts.failedSet || failed;
    const st = opts.settings || settings;
    const p = { mode, mission: { failed_nodes: [...fs] }, sa: {} };
    if (st.available_kW !== "") p.mission.available_kW = +st.available_kW;
    if (st.seed !== "") p.mission.seed = +st.seed;
    if (st.rho !== "") p.sa.rho = +st.rho;
    setRanWith(inputKey(fs, st));
    setBusy(mode);
    try {
      const r = await (await fetch("api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p) })).json();
      setLast(r);
      if (r.ok) setRes((old) => merge(old, r));
      if (!opts.quiet) setScrollTo(MODE_TARGET[mode]);
    } catch (e) {
      setLast({ ok: false, error: "Request failed: " + e.message });
    } finally {
      setBusy(null);
    }
  }

  function toggleFailed(id) {
    const next = new Set(failed);
    next.has(id) ? next.delete(id) : next.add(id);
    setFailed(next);
    run("integrated", { failedSet: next, quiet: true });
  }

  const dirty = ranWith !== null && inputKey(failed, settings) !== ranWith;
  if (!info) return html`<div className="page"><${Message} last=${last} /></div>`;
  return html`
    <${Header} last=${last} />
    <main className="page">
      <section className="hero">
        <h1>Intelligent Iron Man Armor Recovery and Resource Optimization</h1>
        <p>Case study: after a fault in the Mark 85 armor, JARVIS uses three AI methods in sequence.
          <b> Uniform Cost Search</b> finds a safe power route, <b>Simulated Annealing</b> allocates the remaining
          nanomaterial, and a <b>Constraint Satisfaction Problem</b> schedules the laboratory repair work.</p>
      </section>
      <${Controls} info=${info} failed=${failed} setFailed=${setFailed} settings=${settings} setSettings=${setSettings}
        busy=${busy} run=${run} last=${last} dirty=${dirty} />
      <${Message} last=${last} />
      <${Problem} info=${info} />
      <${UcsSection} r=${res} onToggle=${toggleFailed} />
      <${SaSection} r=${res} />
      <${CspSection} r=${res} />
      <${IntegrationSection} r=${res} />
      <${ValidationSection} r=${res} />
      <${ConclusionSection} r=${res} info=${info} />
    </main>
    <${Footer} />`;
}

const inputKey = (fs, st) => JSON.stringify([[...fs].sort(), String(st.available_kW), String(st.seed), String(st.rho)]);

function merge(old, r) {
  const src = MODE_NAME[r.mode];
  const out = { ...old, network: r.network };
  if (r.mode === "integrated") {
    return { network: r.network, ucs: r.ucs, sa: r.sa, csp: r.csp, attempts: r.attempts, health: r.health,
      checks: r.checks, summary: r.summary, status: r.status, success: r.success,
      src: { ucs: src, sa: src, csp: src, integration: src } };
  }
  const stageChecks = (stage) => (r.checks || []).filter((c) => c.stage === stage);
  const keepOther = (stage) => (old.checks || []).filter((c) => c.stage !== stage);
  if (r.mode === "ucs") { out.ucs = r.ucs; out.checks = [...keepOther("UCS"), ...stageChecks("UCS")]; }
  if (r.mode === "sa") { out.sa = r.sa; out.saUp = r.upstream; out.checks = [...keepOther("SA"), ...(r.checks || [])]; }
  if (r.mode === "csp") { out.csp = r.csp; out.cspUp = r.upstream; out.checks = [...keepOther("CSP"), ...(r.checks || [])]; }
  out.src = { ...(old.src || {}), [r.mode]: src };
  return out;
}

function Header({ last }) {
  const [active, setActive] = useState(null);
  useEffect(() => {
    const obs = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: "-40% 0px -55% 0px" });
    SECTIONS.forEach(([id]) => { const el = document.getElementById(id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, []);
  const cls = !last ? "" : last.ok && last.success ? "ok" : "bad";
  return html`<header className="header" id="top"><div className="header-in">
    <div className="logo"><span>JARVIS</span> Mark 85 Recovery</div>
    <nav className="nav">${SECTIONS.map(([id, label]) => html`<a key=${id} href=${"#" + id} className=${active === id ? "active" : ""}>${label}</a>`)}<a href="report.html">Case study report</a></nav>
    <div className=${"badge " + cls} title=${last ? last.status : ""}>${!last ? "Loading…" : !last.ok ? "Error" : last.success ? "✓ " + (last.mode === "integrated" ? "Armor restored" : "Success") : "✗ Not feasible"}</div>
  </div></header>`;
}

function Message({ last }) {
  if (!last) return null;
  if (!last.ok) return html`<div className="msg err"><b>${last.status || "Error"}:</b> ${last.error}</div>`;
  if (last.upstream && last.upstream.rho_auto && last.upstream.rho_log && last.upstream.rho_log.length > 1) {
    return html`<div className="msg info">ρ chosen automatically: ${last.upstream.rho_log.map((x) => `ρ = ${fmt(x.rho, 2)} → ${x.solved ? "feasible" : "infeasible"}`).join(", ")}.</div>`;
  }
  if (!last.success) return html`<div className="msg warn">${last.status}</div>`;
  return null;
}

function Reveal({ id, className = "section", children }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { el.classList.add("shown"); obs.disconnect(); } }, { threshold: 0.08 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return html`<section id=${id} ref=${ref} className=${className + " reveal"}>${children}</section>`;
}

function Source({ text }) { return text ? html`<span className="source">${text}</span>` : null; }
function Stat({ k, v, unit, d, cls = "" }) {
  return html`<div className=${"stat " + cls}><div className="k">${k}</div><div className="v">${v}${unit ? html`<small>${unit}</small>` : null}</div>${d ? html`<div className="d">${d}</div>` : null}</div>`;
}
function Empty({ text }) { return html`<div className="card empty">${text}</div>`; }

function Controls({ info, failed, setFailed, settings, setSettings, busy, run, last, dirty }) {
  const rerunMode = last && last.mode in MODE_NAME ? last.mode : "integrated";
  const failable = info.network.nodes.filter((n) => !["source", "load", "hub"].includes(n.type));
  const set = (k) => (e) => setSettings({ ...settings, [k]: e.target.value });
  const btn = (mode, label, sub, primary) => html`
    <button className=${"btn" + (primary ? " primary" : "") + (last && last.mode === mode ? " current" : "")} disabled=${!!busy} onClick=${() => run(mode)}>
      ${busy === mode ? "Running…" : label}<small>${sub}</small></button>`;
  return html`<div className="card controls">
    <div className="buttons">
      ${btn("integrated", "Run full mission", "UCS → SA → CSP", true)}
      ${btn("ucs", "Uniform Cost Search", "Stage 1 · power route")}
      ${btn("sa", "Simulated Annealing", "Stage 2 · nanomaterial")}
      ${btn("csp", "Constraint Satisfaction Problem", "Stage 3 · lab schedule")}
    </div>
    <div className="settings">
      <label>Failed parts
        <span className="chips">${failable.map((n) => html`<button key=${n.id} className=${"chip" + (failed.has(n.id) ? " failed" : "")} title=${n.label}
          onClick=${() => { const s = new Set(failed); s.has(n.id) ? s.delete(n.id) : s.add(n.id); setFailed(s); }}>${n.id}</button>`)}</span></label>
      <label>Reactor kW <input type="number" min="100" max="1500" step="50" value=${settings.available_kW} onChange=${set("available_kW")} /></label>
      <label>Seed <input type="number" min="0" step="1" value=${settings.seed} onChange=${set("seed")} /></label>
      <label>ρ <input type="number" min="0.1" max="1" step="0.05" placeholder="auto" value=${settings.rho} onChange=${set("rho")} /></label>
      <span className="actions">
        <button className="btn-sm" onClick=${() => { setFailed(new Set(info.defaults.mission.failed_nodes)); setSettings({ available_kW: info.defaults.mission.available_kW, seed: info.defaults.mission.seed, rho: "" }); }}>Reset</button>
        <button className="btn-sm run" disabled=${!dirty || !!busy} onClick=${() => run(rerunMode)}
          title=${dirty ? `Run ${MODE_NAME[rerunMode].toLowerCase()} again with the new values` : "Change a value to enable"}>${busy ? "Running…" : "Run"}</button>
        ${dirty ? html`<span className="changed">values changed</span>` : null}
      </span>
    </div>
  </div>`;
}

function Problem({ info }) {
  const r = info.reactor, n = info.nano;
  return html`<${Reveal} id="problem">
    <h2>1. Problem</h2>
    <p className="lead">${info.mission.trigger}. JARVIS must restore the armor safely within the ${info.mission.horizon_slots} × ${info.mission.slot_minutes}-minute laboratory window (${info.mission.horizon_slots * info.mission.slot_minutes / 60} h).</p>
    <div className="grid2">
      <div className="card"><h3>Subsystems reported by FRIDAY</h3>
        <div className="tbl"><table><thead><tr><th>ID</th><th>Subsystem</th><th className="num">Health</th><th className="num">Load kW</th><th>Status</th></tr></thead>
        <tbody>${info.subsystems.map((s) => html`<tr key=${s.id}><td className="mono">${s.id}</td><td>${s.name}</td><td className="num">${s.health_pct}%</td><td className="num">${s.critical_load_kW}</td><td><span className="tag neutral">${s.status}</span></td></tr>`)}</tbody></table></div></div>
      <div className="card"><h3>Limits and resources</h3>
        <table><tbody>
          <tr><td className="muted">Arc Reactor</td><td>${r.available_output_kW} kW available of ${r.nominal_output_kW} kW (${r.status})</td></tr>
          <tr><td className="muted">Failed part</td><td>${info.network.nodes.filter((x) => x.status === "FAILED").map((x) => `${x.id} (${x.label})`).join(", ")}</td></tr>
          <tr><td className="muted">Route limits</td><td>each edge ≥ ${info.network.required_kW} kW, route heat ≤ ${info.network.thermal_limit_C} °C</td></tr>
          <tr><td className="muted">Nanomaterial</td><td>${n.reserve_NU} NU reserve in ${n.categories.length} functions, armor heat ≤ ${n.thermal_limit_C} °C</td></tr>
          <tr><td className="muted">Laboratory</td><td>${info.lab.tasks.length} tasks, ${info.lab.technicians} technicians, shared robotic arms, bays, charger and test rig</td></tr>
        </tbody></table></div>
    </div>
  <//>`;
}

function UcsSection({ r, onToggle }) {
  const u = r.ucs, net = r.network;
  return html`<${Reveal} id="ucs">
    <h2>2. Uniform Cost Search: power routing <${Source} text=${r.src && r.src.ucs} /></h2>
    <p className="lead">Find the cheapest route from the Arc Reactor (ARC) to the Critical Load Hub (CLH) that avoids failed parts and respects capacity and heat limits.</p>
    <div className="row">
    <div className="method">
      <div className="formula">c(e) = ${net ? net.weights.loss : 1}·loss + ${net ? net.weights.thermal : 0.5}·heat + ${net ? net.weights.switching : 0.4}·switching      g(n') = g(n) + c(n, n')</div>
      <ul><li>The frontier is a priority queue ordered by path cost g; the first time the goal is removed, the route is optimal.</li>
        <li>Hard rules: never enter a FAILED part, every edge needs enough capacity, cumulative heat ≤ limit.</li>
        <li>Output: power budget <b>B = delivered − critical load</b>, which is passed to Simulated Annealing.</li></ul>
    </div>
    ${u && u.found ? html`<div className="stats">
          <${Stat} k="Route cost" v=${fmt(u.cost, 2)} d=${`${u.path.length - 1} hops, optimal`} cls="blue" />
          <${Stat} k="Delivered power" v=${fmt(u.delivered_kW, 0)} unit="kW" d=${`losses ${fmt(u.loss_kW, 0)} kW`} />
          <${Stat} k="Power budget B" v=${fmt(u.budget_kW, 0)} unit="kW" d=${`after ${fmt(u.critical_kW, 0)} kW critical load`} />
          <${Stat} k="Route heat" v=${fmt(u.thermal_C)} unit="°C" d=${`limit ${fmt(net.thermal_limit_C)} °C`} />
          <${Stat} k="Nodes expanded" v=${u.expansions} d=${`${u.generated} generated`} />
          <${Stat} k="Safe routes" v=${u.routes_feasible} unit=${`/ ${u.routes_total}`} d="UCS picks the cheapest" />
        </div>` : !u ? html`<div className="card empty" style=${{ marginTop: 0 }}>Press Uniform Cost Search to compute the route.</div>`
        : html`<div className="msg err" style=${{ marginTop: 0 }}>No safe route exists: every path uses a failed part, overheats, or lacks capacity.</div>`}
    </div>
    ${net ? html`<div className="row big-left">
      <div className="card"><h3>Power network <small>click a converter, switch or bus to fail or repair it</small></h3>
        <${Network} net=${net} path=${u && u.found ? u.path : []} onToggle=${onToggle} />
        <div className="legend"><span><i style=${{ background: BLUE }}></i>chosen route</span><span><i style=${{ background: RED }}></i>failed part</span><span><i style=${{ background: GRAY }}></i>other edges (dashed = too little capacity)</span><span>numbers = edge cost</span></div></div>
      ${u && u.found ? html`<div className="card"><h3>All possible routes <small>${u.routes_feasible} of ${u.routes_total} are safe</small></h3>
          <div className="tbl"><table><thead><tr><th>Route (ARC → … → CLH)</th><th className="num">Cost</th><th className="num">Heat</th><th className="num">kW</th><th>Status</th></tr></thead>
          <tbody>${u.routes.slice(0, 13).map((rt) => {
            const chosen = rt.path.join() === u.path.join();
            const why = rt.uses_failed ? "failed part" : rt.bottleneck < net.required_kW ? "low capacity" : "too hot";
            return html`<tr key=${rt.path.join()} className=${chosen ? "hl" : ""}><td className="mono">${rt.path.slice(1, -1).join(" → ")}</td><td className="num">${fmt(rt.cost, 2)}</td><td className="num">${fmt(rt.thermal)}</td><td className="num">${rt.bottleneck}</td>
              <td>${chosen ? html`<span className="tag blue">chosen</span>` : rt.feasible ? html`<span className="tag ok">safe</span>` : html`<span className="tag no">${why}</span>`}</td></tr>`;
          })}</tbody></table></div></div>` : html`<div></div>`}
    </div>` : null}
  <//>`;
}

const NX = (x) => 60 + x * 172, NY = (y) => 205 - y * 110, NW = 78, NH = 34;
function clip(x1, y1, x2, y2, pad) {
  const dx = x2 - x1, dy = y2 - y1;
  const t = Math.min(dx ? (NW / 2 + pad) / Math.abs(dx) : 1e9, dy ? (NH / 2 + pad) / Math.abs(dy) : 1e9);
  return [x1 + dx * t, y1 + dy * t];
}

function Network({ net, path, onToggle }) {
  const nodes = Object.fromEntries(net.nodes.map((n) => [n.id, n]));
  const route = new Set(path.slice(1).map((v, i) => path[i] + ">" + v));
  const isFailed = (id) => nodes[id].status === "FAILED";
  const edge = (e, kind, key) => {
    const a = nodes[e.u], b = nodes[e.v];
    const [x1, y1] = clip(NX(a.x), NY(a.y), NX(b.x), NY(b.y), 2);
    const [x2, y2] = clip(NX(b.x), NY(b.y), NX(a.x), NY(a.y), 6);
    const st = { route: [BLUE, 3, null, "a-blue"], failed: [RED, 1.3, "5 4", "a-red"], low: [GRAY, 1.2, "5 4", "a-gray"], normal: [GRAY, 1.3, null, "a-gray"], load: [GREEN, 1.3, "2 4", "a-green"] }[kind];
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    return html`<g key=${key}>
      <line x1=${x1} y1=${y1} x2=${x2} y2=${y2} stroke=${st[0]} strokeWidth=${st[1]} strokeDasharray=${st[2]} markerEnd=${`url(#${st[3]})`}>
        <title>${kind === "load" ? `${e.u} → ${e.v} critical load` : `${e.u} → ${e.v}\ncost ${fmt(e.cost, 2)}\nloss ${e.loss} kW, heat ${e.thermal} °C, switching ${e.switch} ms\ncapacity ${e.capacity} kW`}</title></line>
      ${kind !== "load" ? html`<g><rect x=${mx - 14} y=${my - 8} width="28" height="15" rx="3" fill="#fff" />
        <text x=${mx} y=${my + 3.5} textAnchor="middle" fontSize="10" fill=${kind === "route" ? BLUE : MUTED} fontWeight=${kind === "route" ? 700 : 400}>${fmt(e.cost, 1)}</text></g>` : null}
    </g>`;
  };
  const onPath = new Set(path);
  const marker = (id, c) => html`<marker id=${id} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill=${c} /></marker>`;
  return html`<svg viewBox="0 0 960 410" role="img" aria-label="Power distribution network">
    <defs>${marker("a-blue", BLUE)}${marker("a-red", RED)}${marker("a-gray", GRAY)}${marker("a-green", GREEN)}</defs>
    ${net.edges.map((e, i) => {
      const k = e.u + ">" + e.v;
      const kind = route.has(k) ? "route" : isFailed(e.u) || isFailed(e.v) ? "failed" : e.capacity < net.required_kW ? "low" : "normal";
      return edge(e, kind, "e" + i);
    })}
    ${net.load_edges.map(([u, v], i) => edge({ u, v }, "load", "l" + i))}
    ${net.nodes.map((n) => {
      const f = n.status === "FAILED", on = onPath.has(n.id), click = !["source", "load", "hub"].includes(n.type);
      const fill = f ? "#fef2f2" : on ? "#eff6ff" : n.type === "load" ? "#f0fdf4" : "#fff";
      const stroke = f ? RED : on ? BLUE : n.type === "load" ? GREEN : "#d1d5db";
      return html`<g key=${n.id} className=${click ? "node" : ""} onClick=${click ? () => onToggle(n.id) : undefined}>
        <title>${`${n.id}: ${n.label} (${n.status})${click ? `\nclick to ${f ? "repair" : "fail"}` : ""}`}</title>
        <rect x=${NX(n.x) - NW / 2} y=${NY(n.y) - NH / 2} width=${NW} height=${NH} rx="7" fill=${fill} stroke=${stroke} strokeWidth="1.5" />
        <text x=${NX(n.x)} y=${NY(n.y) - 1} textAnchor="middle" fontSize="12" fontWeight="700" fill=${f ? RED : TEXT}>${n.id}</text>
        <text x=${NX(n.x)} y=${NY(n.y) + 11} textAnchor="middle" fontSize="8.5" fill=${f ? RED : MUTED}>${f ? "FAILED" : n.label.length > 17 ? n.label.slice(0, 16) + "…" : n.label}</text>
      </g>`;
    })}
  </svg>`;
}

function SaSection({ r }) {
  const s = r.sa;
  return html`<${Reveal} id="sa">
    <h2>3. Simulated Annealing: nanomaterial allocation <${Source} text=${r.src && r.src.sa} /></h2>
    <p className="lead">Share the ${s ? s.reserve_NU : 1200} NU of nanomaterial between five armor functions to maximise readiness, without exceeding the power, material and heat limits.</p>
    <div className="row">
    <div className="method">
      <div className="formula">J(x) = 100·Σ wᵢ(1 − e^(−xᵢ/sᵢ)) − energy − material − packet waste</div>
      <div className="formula">P(accept worse) = e^(−ΔE/T)      T ← α·T</div>
      <ul><li>Start from the mandatory minimums, then try random moves (transfer, add or remove nano-units).</li>
        <li>Better moves are always accepted; worse moves are sometimes accepted while the temperature is high, which escapes local optima.</li>
        <li>Hard rules: min ≤ xᵢ ≤ max, total ≤ reserve, nano power ≤ ρ·B, route heat + nano heat ≤ armor limit.</li>
        <li>Output: <b>P_res = B − P_nano</b>, the power left for the laboratory, passed to the CSP.</li></ul>
    </div>
    ${!s ? html`<div className="card empty" style=${{ marginTop: 0 }}>Press Simulated Annealing to compute the allocation.</div>` : !s.feasible
      ? html`<div className="msg err" style=${{ marginTop: 0 }}>${s.termination}</div>`
      : html`<div className="stats">
          <${Stat} k="Readiness J*" v=${fmt(s.objective, 2)} d=${`started at ${fmt(s.initial_objective, 2)}`} cls="blue" />
          ${s.hill_climb ? html`<${Stat} k="Hill climbing" v=${fmt(s.hill_climb.objective, 2)} d=${s.objective > s.hill_climb.objective ? `SA better by ${fmt(s.objective - s.hill_climb.objective, 2)}` : "same as SA"} />` : null}
          <${Stat} k="Material used" v=${s.material_NU} unit=${`/ ${s.reserve_NU} NU`} />
          <${Stat} k="Nano power" v=${fmt(s.nano_power_kW, 0)} unit=${`/ ${fmt(s.power_cap_kW, 0)} kW`} d=${`ρ = ${fmt(s.rho, 2)} of B = ${fmt(s.budget_kW, 0)}`} />
          <${Stat} k="Lab power P_res" v=${fmt(s.residual_kW, 0)} unit="kW" d="passed to the CSP" />
          <${Stat} k="Iterations" v=${s.iterations} d=${`${s.improvements} improvements`} />
        </div>`}
    </div>
    ${s && s.feasible ? html`<div className="grid3" style=${{ marginTop: "14px" }}>
          <div className="card"><h3>Allocation <small>bar = result, grey = allowed range</small></h3><${AllocChart} s=${s} /></div>
          <div className="card"><h3>Constraints</h3>
            <${Meter} label="Material ≤ reserve" v=${s.material_NU} cap=${s.reserve_NU} unit="NU" d=${0} />
            <${Meter} label="Nano power ≤ ρ·B" v=${s.nano_power_kW} cap=${s.power_cap_kW} unit="kW" />
            <${Meter} label="Armor heat ≤ limit" v=${s.thermal_C} cap=${s.thermal_limit_C} unit="°C" d=${2} />
            <p className="muted" style=${{ fontSize: "13.5px", marginTop: "14px" }}>Stopped because: ${s.termination}.</p></div>
          <div className="card"><h3>Convergence <small>temperature cools down</small></h3>
            <${SaChart} h=${s.history} />
            <div className="legend"><span><i style=${{ background: BLUE }}></i>best J</span><span><i style=${{ background: GRAY }}></i>current J</span><span><i style=${{ background: AMBER }}></i>temperature</span></div></div>
        </div>` : null}
  <//>`;
}

function Meter({ label, v, cap, unit, d = 1 }) {
  const pct = cap > 0 ? 100 * v / cap : 0;
  return html`<div className=${"meter" + (pct > 100 ? " over" : pct > 95 ? " full" : "")}>
    <div className="row"><span>${label}</span><b className="mono">${fmt(v, d)} / ${fmt(cap, d)} ${unit}</b></div>
    <div className="bar"><span style=${{ width: Math.min(100, pct) + "%" }}></span></div></div>`;
}

function AllocChart({ s }) {
  const cats = s.categories, W = 520, rowH = 44, H = cats.length * rowH + 22, x0 = 140, x1 = W - 50;
  const max = Math.max(...cats.map((c) => c.max));
  const sx = (v) => x0 + (x1 - x0) * v / max;
  return html`<svg viewBox=${`0 0 ${W} ${H}`}>
    ${[0, 100, 200, 300, 400, 500, 600, 700].filter((t) => t <= max).map((t) => html`<g key=${t}><line x1=${sx(t)} x2=${sx(t)} y1="0" y2=${H - 16} stroke=${LINE} /><text x=${sx(t)} y=${H - 3} fontSize="10" fill=${MUTED} textAnchor="middle">${t}</text></g>`)}
    ${cats.map((c, i) => {
      const y = 8 + i * rowH, v = s.allocation[c.id];
      return html`<g key=${c.id}>
        <text x="0" y=${y + 12} fontSize="12" fontWeight="700" fill=${TEXT}>${c.id}</text>
        <text x="0" y=${y + 26} fontSize="10.5" fill=${MUTED}>${c.name}</text>
        <rect x=${sx(c.min)} y=${y} width=${sx(c.max) - sx(c.min)} height="22" rx="3" fill="#f3f4f6" />
        <rect x=${x0} y=${y + 5} width=${sx(v) - x0} height="12" rx="2" fill=${BLUE}><title>${`${c.name}: ${v} NU (allowed ${c.min}–${c.max})`}</title></rect>
        <text x=${sx(v) + 6} y=${y + 15} fontSize="11.5" fontWeight="700" fill=${BLUE}>${v}</text>
      </g>`;
    })}
  </svg>`;
}

function SaChart({ h }) {
  if (!h || !h.length) return null;
  const W = 520, H = 300, m = { l: 40, r: 34, t: 10, b: 24 };
  const maxI = h[h.length - 1].i || 1;
  const js = h.flatMap((p) => [p.cur, p.best]).filter((v) => v != null);
  let lo = Math.min(...js), hi = Math.max(...js);
  const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
  const Tmax = Math.max(...h.map((p) => p.T)) || 1;
  const sx = (i) => m.l + (W - m.l - m.r) * i / maxI;
  const sy = (v) => m.t + (H - m.t - m.b) * (1 - (v - lo) / (hi - lo));
  const sT = (t) => m.t + (H - m.t - m.b) * (1 - t / Tmax);
  const line = (key, f) => h.filter((p) => p[key] != null).map((p, k) => `${k ? "L" : "M"}${sx(p.i).toFixed(1)} ${f(p[key]).toFixed(1)}`).join("");
  const ticks = [0, 1, 2, 3, 4];
  return html`<svg viewBox=${`0 0 ${W} ${H}`}>
    ${ticks.map((k) => { const v = lo + (hi - lo) * k / 4; return html`<g key=${"y" + k}><line x1=${m.l} x2=${W - m.r} y1=${sy(v)} y2=${sy(v)} stroke=${LINE} />
      <text x=${m.l - 6} y=${sy(v) + 3.5} fontSize="10" fill=${MUTED} textAnchor="end">${fmt(v, 1)}</text>
      <text x=${W - m.r + 6} y=${sT(Tmax * k / 4) + 3.5} fontSize="10" fill=${AMBER}>${fmt(Tmax * k / 4, 1)}</text></g>`; })}
    ${[0, 1, 2, 3, 4].map((k) => { const i = Math.round(maxI * k / 4); return html`<text key=${"x" + k} x=${sx(i)} y=${H - 8} fontSize="10" fill=${MUTED} textAnchor="middle">${i}</text>`; })}
    <path d=${line("T", sT)} fill="none" stroke=${AMBER} strokeWidth="1.3" strokeDasharray="5 4" />
    <path d=${line("cur", sy)} fill="none" stroke=${GRAY} strokeWidth="1" />
    <path d=${line("best", sy)} fill="none" stroke=${BLUE} strokeWidth="2.2" />
  </svg>`;
}

function CspSection({ r }) {
  const c = r.csp;
  return html`<${Reveal} id="csp">
    <h2>4. Constraint Satisfaction Problem: laboratory schedule <${Source} text=${r.src && r.src.csp} /></h2>
    <p className="lead">Give every repair task a start time and the equipment it needs, so that no rule is broken and the armor is ready before the deadline.</p>
    <div className="row">
    <div className="method">
      <div className="formula">variable = task,  value = (start slot, equipment units)</div>
      <ul><li><b>C1</b> order between tasks, <b>C2</b> cool-down gap after charging, <b>C3</b> unsafe pairs never overlap, <b>C4</b> one task per equipment unit at a time.</li>
        <li><b>C5</b> total power in every slot ≤ P_res (from SA), <b>C6</b> technicians ≤ ${c ? c.technicians : 2}, <b>C7</b> deadlines.</li>
        <li>Search: backtracking with MRV (fewest values first), degree tie-break and forward checking, then the horizon is tightened to prove the shortest makespan.</li></ul>
    </div>
    ${c && c.solved ? html`<div className="stats two">
          <${Stat} k="Makespan" v=${c.makespan} unit="slots" d=${`${fmt(c.makespan * c.slot_minutes / 60)} h of ${fmt(c.horizon * c.slot_minutes / 60)} h`} cls="blue" />
          <${Stat} k="Lab power limit" v=${fmt(c.power_cap_kW, 0)} unit="kW" d=${`peak use ${fmt(Math.max(...c.power_profile), 0)} kW`} />
          <${Stat} k="Search nodes" v=${c.nodes} d=${`${c.backtracks} backtracks`} />
          <${Stat} k="Shortest possible?" v=${c.makespan_search.some((x) => !x.solved) ? "Yes" : "–"} d=${c.makespan_search.some((x) => !x.solved) ? `${c.makespan - 1} slots is infeasible` : ""} cls="good" />
        </div>` : html`<div></div>`}
    </div>
    ${!c ? html`<${Empty} text="Press Constraint Satisfaction Problem to compute the schedule." />` : !c.solved
      ? html`<div className="msg err"><b>No feasible schedule:</b> ${c.failure_reason}. Leave ρ on auto, or run the full mission so JARVIS replans.</div>`
      : html`<div className="card"><h3>Schedule <small>each column is 30 minutes; text shows the equipment used</small></h3><${Gantt} c=${c} /></div>
        <div className="row big-left" style=${{ marginTop: "14px" }}>
        <div className="card"><h3>Tasks <small>durations come from the UCS route and the SA allocation</small></h3>
          <div className="tbl"><table><thead><tr><th>Task</th><th className="num">Slots</th><th className="num">kW</th><th className="num">Tech</th><th>Slots used</th><th>How the duration is derived</th></tr></thead>
          <tbody>${c.tasks.map((t) => { const sc = c.schedule[t.id]; return html`<tr key=${t.id}><td><b>${t.name}</b></td><td className="num">${t.duration}</td><td className="num">${t.power_kW}</td><td className="num">${t.technicians}</td>
            <td className="mono">${sc ? `${sc.start}–${sc.end}` : "–"}</td><td className="muted">${t.derivation}</td></tr>`; })}</tbody></table></div></div>
        <div className="card"><h3>Power use per slot <small>always under P_res = ${fmt(c.power_cap_kW, 0)} kW</small></h3><${PowerChart} c=${c} /></div>
        </div>`}
  <//>`;
}

function Gantt({ c }) {
  const H = c.horizon, rows = Object.entries(c.schedule).sort((a, b) => a[1].start - b[1].start);
  const W = 1500, x0 = 230, x1 = W - 10, rowH = 32, top = 22, Ht = top + rows.length * rowH + 4, sw = (x1 - x0) / H;
  const sx = (t) => x0 + t * sw;
  return html`<svg viewBox=${`0 0 ${W} ${Ht}`}>
    ${Array.from({ length: H + 1 }, (_, t) => html`<g key=${"t" + t}><line x1=${sx(t)} x2=${sx(t)} y1=${top - 4} y2=${Ht} stroke=${LINE} />
      ${t < H ? html`<text x=${sx(t) + sw / 2} y=${top - 8} fontSize="10" fill=${MUTED} textAnchor="middle">${t}</text>` : null}</g>`)}
    <line x1=${sx(c.makespan)} x2=${sx(c.makespan)} y1=${top - 4} y2=${Ht} stroke=${GREEN} strokeWidth="1.5" strokeDasharray="4 3" />
    ${rows.map(([id, v], i) => {
      const y = top + i * rowH;
      let label = Object.values(v.resources).join(", ");
      const fit = Math.floor((v.duration * sw - 10) / 6);
      if (label.length > fit) label = fit > 3 ? label.slice(0, fit - 1) + "…" : "";
      return html`<g key=${id}>
        <text x="0" y=${y + 19} fontSize="12" fill=${TEXT}>${v.name.length > 30 ? v.name.slice(0, 29) + "…" : v.name}</text>
        <rect x=${sx(v.start) + 1} y=${y + 4} width=${v.duration * sw - 2} height=${rowH - 8} rx="4" fill=${BLUE}>
          <title>${`${v.name}\nslots ${v.start}–${v.end} (${v.duration * c.slot_minutes} min)\n${v.power_kW} kW, ${v.technicians} technician(s)\n${Object.entries(v.resources).map(([k, u]) => `${k}: ${u}`).join(", ")}`}</title></rect>
        <text x=${sx(v.start) + 6} y=${y + 19} fontSize="10.5" fill="#fff" pointerEvents="none">${label}</text>
      </g>`;
    })}
  </svg>`;
}

function PowerChart({ c }) {
  const H = c.horizon, W = 620, x0 = 40, x1 = W - 8, top = 16, ch = 300, sw = (x1 - x0) / H;
  const maxP = Math.max(c.power_cap_kW, ...c.power_profile) * 1.12;
  const sy = (p) => top + ch * (1 - p / maxP);
  return html`<svg viewBox=${`0 0 ${W} ${top + ch + 24}`}>
    ${[0, 0.5, 1].map((k) => html`<g key=${k}><line x1=${x0} x2=${x1} y1=${sy(maxP * k)} y2=${sy(maxP * k)} stroke=${LINE} />
      <text x=${x0 - 6} y=${sy(maxP * k) + 3.5} fontSize="10" fill=${MUTED} textAnchor="end">${fmt(maxP * k, 0)}</text></g>`)}
    ${c.power_profile.map((p, t) => html`<g key=${t}>
      <rect x=${x0 + t * sw + 3} y=${sy(p)} width=${sw - 6} height=${top + ch - sy(p)} rx="2" fill=${BLUE} fillOpacity="0.8"><title>${`slot ${t}: ${fmt(p, 0)} kW, ${c.tech_profile[t]} technician(s)`}</title></rect>
      <text x=${x0 + t * sw + sw / 2} y=${top + ch + 16} fontSize="10" fill=${MUTED} textAnchor="middle">${t}</text></g>`)}
    <line x1=${x0} x2=${x1} y1=${sy(c.power_cap_kW)} y2=${sy(c.power_cap_kW)} stroke=${RED} strokeWidth="1.5" strokeDasharray="6 4" />
    <text x=${x1} y=${sy(c.power_cap_kW) - 5} fontSize="11" fill=${RED} textAnchor="end">limit ${fmt(c.power_cap_kW, 0)} kW</text>
  </svg>`;
}

function IntegrationSection({ r }) {
  const u = r.ucs, s = r.sa, c = r.csp;
  return html`<${Reveal} id="integration">
    <h2>5. Integration and replanning <${Source} text=${r.src && r.src.integration} /></h2>
    <p className="lead">The three methods are linked: each one's output is the next one's input. If a later stage is infeasible, JARVIS changes an earlier decision and tries again.</p>
    <div className="grid2">
      <div className="card"><h3>Data passed between the methods</h3>
        <table><tbody>
          <tr><td className="muted">UCS → SA</td><td>${u && u.found ? html`B = ${fmt(u.delivered_kW, 0)} − ${fmt(u.critical_kW, 0)} = <b>${fmt(u.budget_kW, 0)} kW</b>, route heat ${fmt(u.thermal_C)} °C` : "–"}</td></tr>
          <tr><td className="muted">SA → CSP</td><td>${s && s.feasible ? html`P_res = ${fmt(s.budget_kW, 0)} − ${fmt(s.nano_power_kW, 0)} = <b>${fmt(s.residual_kW, 0)} kW</b>` : "–"}</td></tr>
          <tr><td className="muted">SA → CSP</td><td>${c ? html`task durations from the allocation, e.g. structural restoration ${c.tasks.find((t) => t.id === "STRUCT_REST").duration} slots` : "–"}</td></tr>
          <tr><td className="muted">UCS → CSP</td><td>${u && u.found ? html`route efficiency ${fmt(u.efficiency, 3)} sets the charging time` : "–"}</td></tr>
        </tbody></table></div>
      <div className="card"><h3>Replanning log</h3>
        ${!r.attempts ? html`<p className="muted">Press <b>Run full mission</b> to see how JARVIS replans.</p>` : r.attempts.map((a) => {
          const ok = a.outcome === "feasible", abort = a.action.startsWith("ABORT");
          return html`<div key=${a.number} className=${"attempt" + (ok ? " ok" : abort ? " abort" : "")}>
            <div className="n">${a.number}</div>
            <div><div>ρ = ${fmt(a.rho, 2)}${a.route ? `, route ${a.route.join(" → ")}` : ""}${a.residual_kW != null ? `, P_res = ${fmt(a.residual_kW, 0)} kW` : ""}</div>
              <div className="muted">${a.outcome}</div>
              <div className="act">→ ${a.action}</div></div></div>`;
        })}</div>
    </div>
  <//>`;
}

function ValidationSection({ r }) {
  const checks = r.checks || [];
  const passed = checks.filter((c) => c.passed).length;
  const stages = [...new Set(checks.map((c) => c.stage))];
  return html`<${Reveal} id="validation">
    <h2>6. Validation</h2>
    <p className="lead">Every result is checked again independently from the original data. The plan is only accepted if all checks pass.</p>
    ${!checks.length ? html`<${Empty} text="Run a method to validate its result." />` : html`<div className="card">
      <h3>${passed} of ${checks.length} checks passed ${passed === checks.length ? html`<span className="tag ok">all pass</span>` : html`<span className="tag no">${checks.length - passed} failed</span>`}</h3>
      <div className="checks">${stages.map((st) => html`<${React.Fragment} key=${st}>
        <div className="stage-title">${st}</div>
        ${checks.filter((c) => c.stage === st).map((c, i) => html`<div key=${st + i} className="check"><span className=${"ic " + (c.passed ? "pass" : "fail")}>${c.passed ? "✓" : "✗"}</span>
          <span>${c.check}<span className="det">${c.detail}</span></span></div>`)}
      <//>`)}</div></div>`}
  <//>`;
}

function ConclusionSection({ r, info }) {
  const u = r.ucs, s = r.sa, c = r.csp, full = r.attempts;
  return html`<${Reveal} id="conclusion">
    <h2>7. Results and conclusion</h2>
    ${!full ? html`<${Empty} text="Press Run full mission to produce the final result." />` : html`
      <div className=${"msg " + (r.success ? "info" : "err")}><b>${r.status}</b></div>
      ${r.success && u && s && c ? html`<div className="stats">
        <${Stat} k="Power route" v=${fmt(u.cost, 2)} d=${`cost, B = ${fmt(u.budget_kW, 0)} kW`} cls="blue" />
        <${Stat} k="Readiness J*" v=${fmt(s.objective, 2)} d=${`ρ = ${fmt(s.rho, 2)}`} cls="blue" />
        <${Stat} k="Recovery time" v=${fmt(c.makespan * c.slot_minutes / 60)} unit="h" d=${`${c.makespan} of ${c.horizon} slots`} cls="blue" />
        <${Stat} k="Validation" v=${`${r.summary.passed}/${r.summary.total}`} d="checks passed" cls=${r.summary.all_passed ? "good" : "bad"} />
        <${Stat} k="Attempts" v=${full.length} d=${full.length > 1 ? "replanning used" : "first plan worked"} />
      </div>
      <div className="grid2">
        <div className="card"><h3>Subsystem health <small>before → after (model estimate)</small></h3><${Health} rows=${r.health} /></div>
        <div className="card"><h3>Conclusion</h3>
          <p>UCS routed power through <b>${u.path.join(" → ")}</b>, avoiding the failed ${info.network.nodes.filter((n) => n.status === "FAILED").map((n) => n.id).join(", ")} and staying at ${fmt(u.thermal_C)} °C, which left a budget of ${fmt(u.budget_kW, 0)} kW.</p>
          <p>Simulated Annealing raised readiness from ${fmt(s.initial_objective, 2)} to <b>${fmt(s.objective, 2)}</b> using ${s.material_NU} of ${s.reserve_NU} NU${full.length > 1 ? `, after JARVIS lowered ρ to ${fmt(s.rho, 2)} so the laboratory had enough power` : ""}.</p>
          <p>The CSP scheduled all ${c.tasks.length} tasks in <b>${c.makespan} slots (${fmt(c.makespan * c.slot_minutes / 60)} h)</b>, which is proven to be the shortest possible, within the ${fmt(c.horizon * c.slot_minutes / 60)} h deadline.</p>
          <p>All ${r.summary.total} independent checks passed, so the armor is restored and safe. Combining the three methods works because each one solves the part it suits best: search for routing, optimisation for allocation, and constraint reasoning for scheduling.</p></div>
      </div>` : html`<p className="muted">JARVIS could not commit a safe plan in this scenario, so the armor stays in safe mode for manual repair. See the replanning log above.</p>`}`}
  <//>`;
}

function Health({ rows }) {
  if (!rows) return null;
  const W = 720, rowH = 42, H = rows.length * rowH, x0 = 150, x1 = W - 70;
  const sx = (v) => x0 + (x1 - x0) * v / 100;
  return html`<svg viewBox=${`0 0 ${W} ${H}`}>
    ${rows.map((r, i) => { const y = 6 + i * rowH; return html`<g key=${r.id}>
      <text x="0" y=${y + 15} fontSize="12" fill=${TEXT}>${r.name}</text>
      <rect x=${x0} y=${y} width=${x1 - x0} height="22" rx="3" fill="#f3f4f6" />
      <rect x=${x0} y=${y} width=${sx(r.after) - x0} height="22" rx="3" fill="#bfdbfe" />
      <rect x=${x0} y=${y} width=${sx(r.before) - x0} height="22" rx="3" fill=${BLUE} />
      <text x=${x1 + 6} y=${y + 15} fontSize="11.5" fill=${TEXT}>${r.before}→${fmt(r.after, 0)}%</text></g>`; })}
  </svg>
  <div className="legend"><span><i style=${{ background: BLUE }}></i>before</span><span><i style=${{ background: "#bfdbfe" }}></i>gain after recovery</span></div>`;
}

function Footer() {
  return html`<footer className="site-footer"><div className="footer-in">
    <div className="footer-cols">
      <div><b>JARVIS Mark 85 Recovery</b>
        <p>An academic AI case study that combines search, optimisation and constraint reasoning to restore a damaged armor safely.</p></div>
      <div><b>Methods</b>
        <a href="#ucs">Uniform Cost Search</a><a href="#sa">Simulated Annealing</a><a href="#csp">Constraint Satisfaction Problem</a></div>
      <div><b>Case study</b>
        <a href="report.html">Case study report</a><a href="#problem">Problem</a><a href="#integration">Integration and replanning</a><a href="#validation">Validation</a><a href="#conclusion">Results and conclusion</a></div>
      <div><b>Run locally</b>
        <p><code>python server.py</code><br />Python 3.11 · React 18</p></div>
    </div>
    <div className="footer-bottom">
      <span>Fictional engineering simulation. Mark 85, Arc Reactor, FRIDAY and JARVIS are fictional (Marvel); the algorithms and results are real program output.</span>
      <a href="#top">Back to top ↑</a>
    </div>
  </div></footer>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
