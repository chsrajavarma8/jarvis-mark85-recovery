import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.annealing import NanoAllocationProblem, simulated_annealing
from jarvis.csp import solve_recovery_csp
from jarvis.data_models import Node, load_dataset
from jarvis.pipeline import run_mission
from jarvis.requirements import derive_requirements
from jarvis.ucs import enumerate_simple_paths, uniform_cost_search
from jarvis.validation import validate_csp, validate_sa, validate_ucs

DATA = ROOT / "data" / "mission_dataset.json"


class TestUCS(unittest.TestCase):
    def setUp(self):
        self.ds = load_dataset(DATA)
        self.P = self.ds.reactor["available_output_kW"]

    def test_optimal_against_enumeration(self):
        u = uniform_cost_search(self.ds.network, self.P, self.ds.critical_load_kW)
        best = min(r["cost"] for r in enumerate_simple_paths(self.ds.network) if r["feasible"])
        self.assertTrue(u.found)
        self.assertAlmostEqual(u.path_cost, best, places=6)
        self.assertNotIn("PC1", u.path)
        self.assertTrue(all(c["passed"] for c in validate_ucs(self.ds, u)))

    def test_costs_popped_in_nondecreasing_order(self):
        u = uniform_cost_search(self.ds.network, self.P, self.ds.critical_load_kW)
        gs = [s["g"] for s in u.trace]
        self.assertEqual(gs, sorted(gs))

    def test_excluding_edge_gives_next_route(self):
        u1 = uniform_cost_search(self.ds.network, self.P, self.ds.critical_load_kW)
        u2 = uniform_cost_search(self.ds.network, self.P, self.ds.critical_load_kW,
                                 excluded_edges=[("SW1", "SW2")])
        self.assertTrue(u2.found)
        self.assertGreater(u2.path_cost, u1.path_cost)
        self.assertNotIn(("SW1", "SW2"), list(zip(u2.path, u2.path[1:])))

    def test_thermal_constraint_changes_answer(self):
        blind = uniform_cost_search(self.ds.network, self.P, self.ds.critical_load_kW, enforce_thermal=False)
        safe = uniform_cost_search(self.ds.network, self.P, self.ds.critical_load_kW)
        self.assertGreater(blind.total_thermal_C, self.ds.network.thermal_limit_C)
        self.assertLessEqual(safe.total_thermal_C, self.ds.network.thermal_limit_C)


class TestSA(unittest.TestCase):
    def setUp(self):
        self.ds = load_dataset(DATA)
        self.u = uniform_cost_search(self.ds.network, 1000, self.ds.critical_load_kW)

    def test_feasible_and_reproducible(self):
        prob = NanoAllocationProblem(self.ds.nano, self.u.power_budget_kW, 0.7, self.u.total_thermal_C)
        a = simulated_annealing(prob, self.ds.annealing, seed=85)
        b = simulated_annealing(prob, self.ds.annealing, seed=85)
        self.assertEqual(a.allocation, b.allocation)
        self.assertTrue(all(c["passed"] for c in validate_sa(self.ds, self.u, a)))
        self.assertGreater(a.accepted_worse, 0)

    def test_infeasible_budget_detected(self):
        prob = NanoAllocationProblem(self.ds.nano, 200.0, 0.8, self.u.total_thermal_C)
        r = simulated_annealing(prob, self.ds.annealing, seed=1)
        self.assertFalse(r.feasible)
        self.assertIn("INFEASIBLE", r.termination)


class TestCSP(unittest.TestCase):
    def setUp(self):
        self.ds = load_dataset(DATA)
        u = uniform_cost_search(self.ds.network, 1000, self.ds.critical_load_kW)
        prob = NanoAllocationProblem(self.ds.nano, u.power_budget_kW, 0.7, u.total_thermal_C)
        sa = simulated_annealing(prob, self.ds.annealing, seed=85)
        self.req = derive_requirements(self.ds, u, sa)

    def test_heuristic_and_plain_agree_on_feasibility(self):
        h, _, _ = solve_recovery_csp(self.req, self.ds.lab)
        p, _, _ = solve_recovery_csp(self.req, self.ds.lab, use_mrv=False, use_degree=False, use_fc=False)
        self.assertTrue(h.solved and p.solved)
        self.assertLessEqual(h.nodes, p.nodes)
        self.assertTrue(all(c["passed"] for c in validate_csp(self.ds, self.req, h)))
        self.assertTrue(all(c["passed"] for c in validate_csp(self.ds, self.req, p)))

    def test_tight_horizon_is_infeasible(self):
        r, _, _ = solve_recovery_csp(self.req, self.ds.lab, horizon=10)
        self.assertFalse(r.solved)


class TestIntegratedMission(unittest.TestCase):
    def test_nominal_mission_replans_then_succeeds(self):
        ds = load_dataset(DATA)
        out = run_mission(ds, verbose=False)
        self.assertTrue(out.success)
        self.assertGreaterEqual(len(out.attempts), 2)
        self.assertIn("CSP infeasible", out.attempts[0].outcome)
        self.assertTrue(all(c["passed"] for c in out.checks))

    def test_stress_failed_secondary_converter(self):
        ds = load_dataset(DATA)
        ds.network.nodes["PC2"] = replace(ds.network.nodes["PC2"], status="FAILED")
        out = run_mission(ds, verbose=False)
        if out.success:
            self.assertNotIn("PC2", out.ucs.path)
            self.assertTrue(all(c["passed"] for c in out.checks))
        else:
            self.assertTrue(any("exclude" in a.action or "ABORT" in a.action for a in out.attempts))


if __name__ == "__main__":
    unittest.main()
