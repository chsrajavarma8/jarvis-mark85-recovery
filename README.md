# JARVIS Mark 85 Recovery – AI Case Study Lab

**Uniform Cost Search + Simulated Annealing + Constraint Satisfaction, integrated into one armor recovery mission.**

This lab solves tasks 3, 7 and 11 of the college case study *Avengers – Iron Man Technology Ecosystem: 12 AI Algorithm Tasks Based on Stark Engineering Systems* (full brief in [`docs/case_study_source.md`](docs/case_study_source.md)). Instead of three separate exercises, the three algorithms are chained so that each one's output becomes the next one's input, with automatic replanning and independent validation.

> Fictional engineering simulation. Mark 85, Arc Reactor, FRIDAY and JARVIS are fictional (Marvel). All numbers in the dataset are invented for teaching; the algorithms, traces and results are real program output.

## Tech stack

| Layer | Technology |
|---|---|
| Algorithms | Python 3.11 standard library – `heapq` (UCS priority queue), `random` + `math` (Simulated Annealing), backtracking with MRV, degree heuristic and forward checking (CSP) |
| Backend | Python `http.server` (`ThreadingHTTPServer`), JSON API in `jarvis/api.py` – no web framework, no database |
| Frontend | React 18 + htm, served locally from `web/vendor/` – no Node.js, npm or build step |
| Figures | matplotlib, networkx |
| Report document | python-docx (DOCX), Microsoft Word export (PDF) |
| Tests | `unittest` – 19 unit, integration, API and server tests |

No API keys, accounts, environment variables or external services are used. Everything runs offline on `127.0.0.1`.

## Backend

`server.py` serves the two pages and four endpoints. Every request reloads the shared dataset, applies the requested settings to a fresh copy and runs the solvers, so runs never affect each other.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/dataset` | GET | Mission description and default settings |
| `/api/run` | POST | Run one mode: `integrated`, `ucs`, `sa` or `csp`, with optional failed parts, reactor output, seed and ρ |
| `/api/performance` | GET | Full mission plus the performance study (SA vs hill climbing, CSP heuristics, routing strategies), cached after the first call |
| `/docs/case_study_source.md` | GET | The college brief shown on the report page |

Example request:

```bash
curl -X POST http://127.0.0.1:8085/api/run -H "Content-Type: application/json" \
     -d '{"mode": "integrated", "mission": {"failed_nodes": ["PC1"], "seed": 85}}'
```

Request bodies are limited to 64 KB, bad input returns an error message instead of crashing, and only files inside `web/` can be served.

## The problem

FRIDAY reports a fault in the Mark 85: primary converter PC1 has failed, the Arc Reactor is derated to 1000 kW, only 1200 NU of nanomaterial remain and five subsystems are damaged. JARVIS must restore the armor safely within an 8-hour laboratory window.

| Stage | Case study task | What it decides | Passes on |
|---|---|---|---|
| 1 | Task 3 · Uniform Cost Search | Cheapest safe power route from the Arc Reactor to the critical load hub, avoiding failed parts, capacity limits and the route heat limit | Power budget **B** and route efficiency |
| 2 | Task 7 · Simulated Annealing | Allocation of the nanomaterial reserve over five armor functions under ρ·B, the reserve, mandatory minimums and the armor heat limit | Lab power **P_res** and repair workload |
| 3 | Task 11 · Constraint Satisfaction | Schedule of nine lab tasks under precedence, safety separation, equipment exclusivity and compatibility, power, technicians and deadlines | Final recovery plan |

If a stage is infeasible, JARVIS replans (lowers ρ or excludes the weakest route edge) and runs the mission again. Every result is then re-checked independently (36 checks).

## Results (reference run, seed 85)

| Measure | Value |
|---|---|
| Power route | ARC → PC2 → SW1 → SW2 → BUS_B → CLH, cost 44.20, heat 14.0 °C, budget B = 530 kW |
| Replanning | Attempt 1 (ρ = 0.80) infeasible: charging needs 120 kW > P_res 111.9 kW; attempt 2 uses ρ = 0.70 |
| Nanomaterial | SP 320 · ES 122 · FS 125 · SR 174 · SN 100 NU, readiness J* = 50.831, P_res = 160 kW |
| Schedule | 15 slots (7.5 h of 8 h), proven minimal because 14 slots is infeasible |
| Validation | 36 / 36 checks pass – **armor restored, operational and safe** |
| SA vs hill climbing | Mean J 50.77 vs 47.48 over 30 seeds, SA better in 30 / 30 |
| CSP heuristics | MRV + degree + FC: 10 nodes, 0 backtracks; plain backtracking: 3828 nodes, 1097 backtracks |

## Run it

Requires Python 3.10 or newer (tested with 3.11.9 on Windows 11).

```bash
python -m pip install -r requirements.txt

python server.py                         # interactive case study page at http://127.0.0.1:8085
python main.py                           # full mission in the console + exports + 10 figures
python main.py --quick --no-plots        # fast console run
python main.py --scenario pc2-failure    # stress test: a second converter fails, JARVIS aborts safely
python -m unittest discover -s tests -v  # 19 tests
python scripts/build_case_study.py       # rebuild docs/JARVIS_Case_Study.docx from outputs/
```

The web page needs no Node.js or build step; React is served locally from `web/vendor/`.

* **Home page** – the case study with live results: four buttons run the full mission or one method (Uniform Cost Search, Simulated Annealing, Constraint Satisfaction Problem). Click a converter, switch or bus on the network map to fail or repair it.
* **Report page** (`/report.html`) – the full college brief, our approach, a point-by-point checklist of the brief, the issues we solved and live measurements.

## Repository layout

```
jarvis_recovery/
├── main.py                  console entry point (mission, exports, figures)
├── server.py                local web server for the case study pages
├── requirements.txt
├── data/
│   └── mission_dataset.json the single shared dataset
├── jarvis/                  solver package
│   ├── data_models.py       dataset loader and stage result types
│   ├── ucs.py               Stage 1 – Uniform Cost Search
│   ├── annealing.py         Stage 2 – Simulated Annealing
│   ├── requirements.py      UCS + SA results → CSP inputs
│   ├── csp.py               Stage 3 – backtracking, MRV, degree heuristic, forward checking
│   ├── pipeline.py          orchestration and controlled replanning
│   ├── validation.py        independent re-check of every constraint
│   ├── experiments.py       SA vs hill climbing, CSP heuristics, routing strategies
│   ├── reporting.py         console report, CSV / JSON exports
│   ├── visualization.py     figures and dashboard
│   └── api.py               JSON interface for the web pages
├── web/                     home page, report page, styles, React (vendor/)
├── tests/                   unit, integration, interface and server tests
├── scripts/
│   └── build_case_study.py  builds the case study document from real outputs
├── docs/
│   ├── case_study_source.md the college brief
│   ├── JARVIS_Case_Study.docx
│   └── JARVIS_Case_Study.pdf
└── outputs/                 results.json, CSV exports, traces, figures/
```

## Coverage of the brief

| Task | Core task | Challenges | Extension |
|---|---|---|---|
| 3 · UCS | Done | Done | Partial – loads share one hub route; independent per-load paths not compared |
| 7 · Simulated Annealing | Done | Done, except the total is kept ≤ reserve rather than exactly equal | Not done – cooling-schedule comparison and reduced reserve |
| 11 · CSP | Done (nine lab activities; Veronica, satellite, EDITH and B.A.R.F. activities not modelled) | Done, all constraints hard | Not done – urgent repair re-scheduling |

The detailed checklist with evidence for every point is on the report page.
