"""Phase 10 tests: ETA training/prediction, crowd prediction, anomalies, evaluation."""
import csv
import math
import random
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from commuter.models import Incident
from core.models import Membership, Organisation, User
from fleet.models import Route, Stop, Vehicle
from intelligence import training
from intelligence.services import detect_anomalies, predict_eta_minutes
from tracking.models import ETAPrediction, LocationHistory, OccupancyRecord

ROUTE_NAME = "Test Route"
DISTANCE_MAP = {(ROUTE_NAME, "A"): 0.0, (ROUTE_NAME, "B"): 2.0,
                (ROUTE_NAME, "C"): 5.0, (ROUTE_NAME, "D"): 9.0}
STOPS_SEQ = ["A", "B", "C", "D"]


def write_synthetic_csv(path, days=12, seed=7):
    """Deterministic CSV with a learnable peak-hour pattern (synthetic test data)."""
    rng = random.Random(seed)
    rows = []
    base_day = datetime(2026, 11, 1, tzinfo=dt_timezone.utc)
    for d in range(days):
        day = base_day + timedelta(days=d)
        for hour in range(7, 22):
            speed = 18.0 if hour in (8, 9, 17, 18, 19) else 32.0
            seq = STOPS_SEQ if hour % 2 == 0 else list(reversed(STOPS_SEQ))
            t = day.replace(hour=hour, minute=5)
            pax = 10
            for a, b in zip(seq, seq[1:]):
                dist = abs(DISTANCE_MAP[(ROUTE_NAME, b)] - DISTANCE_MAP[(ROUTE_NAME, a)])
                duration = dist / speed * 60 + 0.5 + rng.uniform(-0.2, 0.2)
                pax = max(0, min(40, pax + rng.randint(-3, 4)))
                rows.append({
                    "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "vehicle": "TEST-001", "route": ROUTE_NAME,
                    "stop_from": a, "stop_to": b,
                    "duration_minutes": round(duration, 2),
                    "passengers": pax, "day_of_week": day.weekday(), "hour": hour,
                })
                t += timedelta(minutes=duration)
    rows.sort(key=lambda r: r["timestamp"])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def make_route_fixture(org):
    route = Route.objects.create(
        organisation=org, name=ROUTE_NAME, start_point="A", end_point="D",
        total_distance_km=9.0,
        polyline=[[31.255, 75.705], [31.240, 75.730], [31.200, 75.790]])
    stops = {}
    for i, name in enumerate(STOPS_SEQ, start=1):
        stops[name] = Stop.objects.create(
            route=route, name=name, order=i,
            distance_from_start_km=DISTANCE_MAP[(ROUTE_NAME, name)],
            latitude=31.25 - i * 0.01, longitude=75.70 + i * 0.02)
    return route, stops


class TrainingPipelineTests(TestCase):
    def test_training_produces_model_and_honest_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "history.csv"
            n = write_synthetic_csv(csv_path)
            self.assertGreater(n, 500)
            model_path, metrics_path = Path(tmp) / "m.joblib", Path(tmp) / "m.json"
            metrics = training.train_eta_model(
                csv_path, model_path=model_path, metrics_path=metrics_path,
                distance_map=DISTANCE_MAP)
            self.assertTrue(model_path.exists())
            self.assertTrue(metrics_path.exists())
            for method in ("baseline", "ml"):
                self.assertTrue(math.isfinite(metrics[method]["mae"]))
                self.assertTrue(math.isfinite(metrics[method]["rmse"]))
                self.assertGreater(metrics[method]["n"], 0)
            # Peak-hour pattern is learnable: ML must beat the 25 km/h baseline.
            self.assertLess(metrics["ml"]["mae"], metrics["baseline"]["mae"])
            self.assertIn("SYNTHETIC", metrics["data_source"])


class PredictServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tmp = tempfile.mkdtemp()
        csv_path = Path(cls.tmp) / "history.csv"
        write_synthetic_csv(csv_path)
        cls.model_path = str(Path(cls.tmp) / "eta_model.joblib")
        training.train_eta_model(csv_path, model_path=cls.model_path,
                                 metrics_path=str(Path(cls.tmp) / "m.json"),
                                 distance_map=DISTANCE_MAP)
        cls.org = Organisation.objects.create(name="Predict Org")
        cls.route, cls.stops = make_route_fixture(cls.org)
        cls.vehicle = Vehicle.objects.create(
            organisation=cls.org, registration_number="PRED-001", capacity=40,
            current_route=cls.route, distance_covered_km=0.5, speed_kmph=30.0,
            passengers_onboard=10, status="active")

    def test_predict_with_model_returns_positive_float(self):
        with override_settings(INTELLIGENCE_ETA_MODEL_PATH=self.model_path):
            eta = predict_eta_minutes(self.vehicle, self.stops["D"])
        self.assertIsNotNone(eta)
        self.assertGreater(eta, 0)

    def test_predict_without_model_returns_none(self):
        with override_settings(INTELLIGENCE_ETA_MODEL_PATH="/nonexistent/eta_model.joblib"):
            self.assertIsNone(predict_eta_minutes(self.vehicle, self.stops["D"]))

    def test_predict_passed_stop_returns_none(self):
        with override_settings(INTELLIGENCE_ETA_MODEL_PATH=self.model_path):
            self.assertIsNone(predict_eta_minutes(self.vehicle, self.stops["A"]))


class LiveETAMethodTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tmp = tempfile.mkdtemp()
        csv_path = Path(cls.tmp) / "history.csv"
        write_synthetic_csv(csv_path)
        cls.model_path = str(Path(cls.tmp) / "eta_model.joblib")
        training.train_eta_model(csv_path, model_path=cls.model_path,
                                 metrics_path=str(Path(cls.tmp) / "m.json"),
                                 distance_map=DISTANCE_MAP)

    def setUp(self):
        self.org = Organisation.objects.create(name="LiveETA Org")
        self.user = User.objects.create_user(email="eta@test.com", password="Password@1")
        Membership.objects.create(user=self.user, organisation=self.org, role="commuter")
        self.route, self.stops = make_route_fixture(self.org)
        self.vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="LIVE-001", capacity=40,
            current_route=self.route, distance_covered_km=0.5, speed_kmph=30.0,
            passengers_onboard=10, status="active")
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "eta@test.com", "password": "Password@1"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_live_eta_uses_ml_when_model_present(self):
        with override_settings(INTELLIGENCE_ETA_MODEL_PATH=self.model_path):
            r = self.client.get(f"/api/v1/live/eta/?stop_id={self.stops['D'].id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["method"], "ml")
        self.assertGreater(r.data[0]["eta_minutes"], 0)
        self.assertEqual(ETAPrediction.objects.first().method, "ml")

    def test_live_eta_falls_back_to_baseline_without_model(self):
        with override_settings(INTELLIGENCE_ETA_MODEL_PATH="/nonexistent/eta_model.joblib"):
            r = self.client.get(f"/api/v1/live/eta/?stop_id={self.stops['D'].id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["method"], "baseline")
        self.assertEqual(r.data[0]["eta_minutes"], 17.0)  # 8.5 km @ 30 km/h


class CrowdPredictionTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Crowd Org")
        self.other_org = Organisation.objects.create(name="Other Org")
        self.user = User.objects.create_user(email="crowd@test.com", password="Password@1")
        Membership.objects.create(user=self.user, organisation=self.org, role="commuter")
        self.route, self.stops = make_route_fixture(self.org)
        self.vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="CROWD-001", capacity=40,
            current_route=self.route, status="active")
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "crowd@test.com", "password": "Password@1"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.hour = timezone.localtime(timezone.now()).hour

    def test_insufficient_data_returns_null_level(self):
        r = self.client.get(f"/api/v1/intelligence/crowd-prediction/?route_id={self.route.id}&hour={self.hour}")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["level"])
        self.assertEqual(r.data["reason"], "insufficient data")
        self.assertEqual(r.data["samples"], 0)

    def test_prediction_from_history(self):
        now = timezone.now()
        for i in range(6):  # 36/40 = 90% occupancy -> high
            OccupancyRecord.objects.create(
                vehicle=self.vehicle, passengers_onboard=36,
                recorded_at=now - timedelta(days=i))
        r = self.client.get(f"/api/v1/intelligence/crowd-prediction/?route_id={self.route.id}&hour={self.hour}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["level"], "high")
        self.assertEqual(r.data["samples"], 6)
        self.assertAlmostEqual(r.data["avg_occupancy_percent"], 90.0, places=1)

    def test_other_org_route_404(self):
        other_route, _ = make_route_fixture(self.other_org)
        r = self.client.get(f"/api/v1/intelligence/crowd-prediction/?route_id={other_route.id}&hour={self.hour}")
        self.assertEqual(r.status_code, 404)


class AnomalyDetectionTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Anomaly Org")
        self.admin = User.objects.create_user(email="admin@test.com", password="Password@1")
        Membership.objects.create(user=self.admin, organisation=self.org, role="org_admin")
        self.route, self.stops = make_route_fixture(self.org)
        self.now = timezone.now()

    def _vehicle(self, reg):
        return Vehicle.objects.create(
            organisation=self.org, registration_number=reg, capacity=40,
            current_route=self.route, status="active")

    def _point(self, vehicle, lat, lng, speed, when, dist=1.0):
        return LocationHistory.objects.create(
            vehicle=vehicle, latitude=lat, longitude=lng,
            distance_covered_km=dist, speed_kmph=speed, recorded_at=when)

    def test_deviation_stale_and_speed_jump_flagged_and_deduped(self):
        # Vehicle 1: fresh points, one far off-route -> route_deviation.
        v1 = self._vehicle("ANOM-001")
        self._point(v1, 31.255, 75.705, 30, self.now - timedelta(seconds=90))
        self._point(v1, 31.240, 75.730, 30, self.now - timedelta(seconds=30))
        self._point(v1, 31.320, 75.850, 30, self.now - timedelta(seconds=5))  # ~15 km off-route

        # Vehicle 2: last point 10 min ago -> stale_gps.
        v2 = self._vehicle("ANOM-002")
        self._point(v2, 31.255, 75.705, 25, self.now - timedelta(minutes=10))

        # Vehicle 3: speed 10 -> 90 km/h between points -> speed_jump.
        v3 = self._vehicle("ANOM-003")
        self._point(v3, 31.255, 75.705, 10, self.now - timedelta(seconds=60))
        self._point(v3, 31.250, 75.710, 90, self.now - timedelta(seconds=10))

        summary = detect_anomalies(hours=2, now=self.now, create=True)
        self.assertEqual(summary["route_deviation"], 1)
        self.assertEqual(summary["stale_gps"], 1)
        self.assertEqual(summary["speed_jump"], 1)
        self.assertEqual(summary["incidents_created"], 3)
        types = set(Incident.objects.values_list("type", flat=True))
        self.assertEqual(types, {"route_deviation", "stale_gps", "speed_jump"})

        # Second run inside 30 min: deduped, no new incidents.
        summary2 = detect_anomalies(hours=2, now=self.now, create=True)
        self.assertEqual(summary2["incidents_created"], 0)
        self.assertEqual(summary2["deduped"], 3)
        self.assertEqual(Incident.objects.count(), 3)


class EvaluateETAsTests(TestCase):
    def test_evaluate_fills_actual_from_arrival(self):
        org = Organisation.objects.create(name="Eval Org")
        route, stops = make_route_fixture(org)
        vehicle = Vehicle.objects.create(
            organisation=org, registration_number="EVAL-001", capacity=40,
            current_route=route, status="active")
        pred = ETAPrediction.objects.create(
            vehicle=vehicle, stop=stops["C"], predicted_eta_minutes=10.0, method="ml")
        LocationHistory.objects.create(
            vehicle=vehicle, latitude=31.24, longitude=75.73,
            distance_covered_km=5.1, speed_kmph=20,
            recorded_at=pred.created_at + timedelta(minutes=12))
        call_command("evaluate_etas")
        pred.refresh_from_db()
        self.assertAlmostEqual(pred.actual_eta_minutes, 12.0, places=1)
        self.assertIsNotNone(pred.evaluated_at)
