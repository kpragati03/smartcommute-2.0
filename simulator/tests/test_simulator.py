"""Unit tests for the SmartCommute 2.0 simulator (stdlib unittest only).

Run:  python -m unittest discover -s tests -v
  or: python tests/test_simulator.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import simulator as sim


class HaversineTests(unittest.TestCase):
    def test_one_degree_latitude(self):
        # 1 degree of latitude ~= 111.19 km.
        d = sim.haversine_km(31.0, 75.0, 32.0, 75.0)
        self.assertAlmostEqual(d, 111.19, delta=0.5)

    def test_zero_distance(self):
        self.assertEqual(sim.haversine_km(31.255, 75.705, 31.255, 75.705), 0.0)

    def test_known_short_hop(self):
        # LPU Main Gate -> Law Gate from the contract coords: ~0.76 km.
        d = sim.haversine_km(31.2550, 75.7050, 31.2490, 75.7010)
        self.assertAlmostEqual(d, 0.76, delta=0.15)


class PolylineTests(unittest.TestCase):
    def setUp(self):
        # Simple 3-point polyline along a meridian: 0, ~111.19, ~222.39 km.
        self.poly = sim.Polyline([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)])

    def test_total_length(self):
        self.assertAlmostEqual(self.poly.total_km, 222.39, delta=1.0)

    def test_start_endpoint(self):
        self.assertEqual(self.poly.interpolate(0), (0.0, 0.0))

    def test_end_endpoint(self):
        self.assertEqual(self.poly.interpolate(self.poly.total_km), (2.0, 0.0))

    def test_clamped_beyond_ends(self):
        self.assertEqual(self.poly.interpolate(-5), (0.0, 0.0))
        self.assertEqual(self.poly.interpolate(99999), (2.0, 0.0))

    def test_midpoint_of_first_segment(self):
        lat, lng = self.poly.interpolate(self.poly.cumulative_km[1] / 2)
        self.assertAlmostEqual(lat, 0.5, delta=0.01)
        self.assertAlmostEqual(lng, 0.0, delta=0.01)

    def test_segment_join(self):
        lat, _ = self.poly.interpolate(self.poly.cumulative_km[1])
        self.assertAlmostEqual(lat, 1.0, delta=0.01)


class PassengerClampTests(unittest.TestCase):
    def test_clamp_high(self):
        self.assertEqual(sim.clamp_passengers(99, 40), 40)

    def test_clamp_low(self):
        self.assertEqual(sim.clamp_passengers(-3, 40), 0)

    def test_within_range(self):
        self.assertEqual(sim.clamp_passengers(17, 40), 17)


class ConfigFallbackTests(unittest.TestCase):
    def test_missing_config_falls_back_to_demo(self):
        config, from_file = sim.load_config("/nonexistent/config.json")
        self.assertFalse(from_file)
        regs = [v["registration_number"] for v in config["vehicles"]]
        self.assertEqual(regs, ["PB-10-AX-101", "PB-10-AX-102", "PB-10-BX-201"])
        self.assertEqual(config["api_base_url"], sim.DEFAULT_API_BASE_URL)

    def test_demo_stops_have_increasing_distances(self):
        config = sim.demo_config()
        for vehicle in config["vehicles"]:
            dists = [s["distance_from_start_km"] for s in vehicle["stops"]]
            self.assertEqual(dists, sorted(dists))
            self.assertEqual(dists[0], 0.0)
            self.assertEqual(len(vehicle["route_polyline"]), len(vehicle["stops"]))

    def test_env_key_override(self):
        os.environ["DEVICE_KEY_PB_10_AX_101"] = "env-secret-key"
        try:
            config = sim.demo_config()
            key = config["vehicles"][0]["device_key"]
            self.assertEqual(key, "env-secret-key")
        finally:
            del os.environ["DEVICE_KEY_PB_10_AX_101"]

    def test_cli_override_beats_env(self):
        os.environ["DEVICE_KEY_PB_10_AX_101"] = "env-secret-key"
        try:
            config = sim.demo_config({"PB-10-AX-101": "cli-key"})
            self.assertEqual(config["vehicles"][0]["device_key"], "cli-key")
        finally:
            del os.environ["DEVICE_KEY_PB_10_AX_101"]


class HistoryExportTests(unittest.TestCase):
    def test_export_deterministic_and_shaped(self):
        import tempfile
        config = sim.demo_config()
        with tempfile.TemporaryDirectory() as tmp:
            p1, p2 = os.path.join(tmp, "a.csv"), os.path.join(tmp, "b.csv")
            n1 = sim.export_history(config, p1, days=3, seed=7)
            n2 = sim.export_history(config, p2, days=3, seed=7)
            self.assertEqual(n1, n2)
            self.assertGreater(n1, 0)
            with open(p1, encoding="utf-8") as fh:
                lines1 = fh.read()
            with open(p2, encoding="utf-8") as fh:
                lines2 = fh.read()
            self.assertEqual(lines1, lines2)  # deterministic with same seed
            header = lines1.splitlines()[0]
            self.assertEqual(
                header,
                "timestamp,vehicle,route,stop_from,stop_to,"
                "duration_minutes,passengers,day_of_week,hour")


if __name__ == "__main__":
    unittest.main()
