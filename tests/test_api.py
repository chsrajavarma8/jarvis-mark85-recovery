import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis import api


def strict_json(obj):
    return json.loads(json.dumps(obj, allow_nan=False))


class TestApiModes(unittest.TestCase):
    def test_integrated_reference_run(self):
        r = strict_json(api.run({"mode": "integrated"}))
        self.assertTrue(r["ok"] and r["success"])
        self.assertEqual(r["ucs"]["path"], ["ARC", "PC2", "SW1", "SW2", "BUS_B", "CLH"])
        self.assertEqual(len(r["attempts"]), 2)
        self.assertEqual(r["csp"]["makespan"], 15)
        self.assertEqual(r["summary"], {"passed": 36, "total": 36, "all_passed": True})

    def test_single_methods(self):
        for mode, key in (("ucs", "ucs"), ("sa", "sa"), ("csp", "csp")):
            r = strict_json(api.run({"mode": mode}))
            self.assertTrue(r["ok"] and r["success"], (mode, r.get("status")))
            self.assertIn(key, r)

    def test_csp_auto_rho_matches_replanner(self):
        r = api.run({"mode": "csp"})
        self.assertTrue(r["upstream"]["rho_auto"])
        self.assertAlmostEqual(r["upstream"]["rho"], 0.7)
        fixed = api.run({"mode": "csp", "sa": {"rho": 0.8}})
        self.assertFalse(fixed["success"])

    def test_sa_manual_budget_and_hill_climb(self):
        r = api.run({"mode": "sa", "sa": {"budget_kW": 600, "compare_hc": True}})
        self.assertEqual(r["upstream"]["budget_source"], "manual")
        self.assertAlmostEqual(r["sa"]["power_cap_kW"], 0.8 * 600)
        self.assertIn("hill_climb", r["sa"])

    def test_stress_scenario_aborts_safely(self):
        r = strict_json(api.run({"mode": "integrated", "mission": {"failed_nodes": ["PC1", "PC2"]}}))
        self.assertTrue(r["ok"])
        self.assertFalse(r["success"])
        self.assertTrue(r["status"].startswith("RECOVERY"))

    def test_bad_input_is_reported_not_raised(self):
        for params in ({"mode": "nope"}, {"mission": {"failed_nodes": ["ARC"]}},
                       {"sa": {"rho": 5}}, {"ucs": {"w_loss": "abc"}}):
            r = api.run(params)
            self.assertFalse(r["ok"], params)
            self.assertTrue(r["error"])

    def test_dataset_info(self):
        info = strict_json(api.dataset_info())
        self.assertEqual(len(info["network"]["nodes"]), 16)
        self.assertEqual(info["defaults"]["mission"]["failed_nodes"], ["PC1"])


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer
        import server
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_index_and_run(self):
        with urllib.request.urlopen(self.base + "/") as resp:
            self.assertIn(b"JARVIS Case Study", resp.read())
        req = urllib.request.Request(self.base + "/api/run", data=json.dumps({"mode": "ucs"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertTrue(json.load(resp)["success"])

    def test_no_path_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(self.base + "/../server.py")
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
