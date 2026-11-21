from rest_framework.test import APITestCase
from core.models import Organisation, User, Membership
from fleet.models import Route, Stop, Vehicle, Device, hash_device_key
from tracking.models import LocationHistory, OccupancyRecord
from tracking.services import baseline_eta


class TelemetryTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Tele Org")
        self.route = Route.objects.create(organisation=self.org, name="TR", start_point="A", end_point="B", total_distance_km=10)
        self.vehicle = Vehicle.objects.create(organisation=self.org, registration_number="TEL-001", capacity=40, current_route=self.route)
        self.raw_key = "test-device-key-123"
        Device.objects.create(vehicle=self.vehicle, device_key_hash=hash_device_key(self.raw_key))

    def _payload(self, **kw):
        base = {"latitude": 31.25, "longitude": 75.70, "distance_covered_km": 2.0,
                "speed_kmph": 30.0, "passengers_onboard": 10}
        base.update(kw)
        return base

    def test_valid_telemetry_writes_history(self):
        r = self.client.post("/api/v1/devices/telemetry/", self._payload(),
                             format="json", HTTP_X_DEVICE_KEY=self.raw_key)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(LocationHistory.objects.count(), 1)
        self.assertEqual(OccupancyRecord.objects.count(), 1)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.passengers_onboard, 10)
        self.assertEqual(self.vehicle.speed_kmph, 30.0)

    def test_bad_key_401(self):
        r = self.client.post("/api/v1/devices/telemetry/", self._payload(),
                             format="json", HTTP_X_DEVICE_KEY="wrong-key")
        self.assertEqual(r.status_code, 401)

    def test_missing_key_401(self):
        r = self.client.post("/api/v1/devices/telemetry/", self._payload(), format="json")
        self.assertEqual(r.status_code, 401)

    def test_passengers_over_capacity_400(self):
        r = self.client.post("/api/v1/devices/telemetry/", self._payload(passengers_onboard=41),
                             format="json", HTTP_X_DEVICE_KEY=self.raw_key)
        self.assertEqual(r.status_code, 400)

    def test_invalid_latitude_400(self):
        r = self.client.post("/api/v1/devices/telemetry/", self._payload(latitude=95),
                             format="json", HTTP_X_DEVICE_KEY=self.raw_key)
        self.assertEqual(r.status_code, 400)


class ETATests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="ETA Org")
        self.route = Route.objects.create(organisation=self.org, name="ER", start_point="A", end_point="B", total_distance_km=12.5)
        self.stop = Stop.objects.create(route=self.route, name="Mid", order=2, distance_from_start_km=6.0, latitude=31.24, longitude=75.73)
        self.vehicle = Vehicle.objects.create(organisation=self.org, registration_number="ETA-001", capacity=40,
                                              current_route=self.route, distance_covered_km=2.0, speed_kmph=24.0)

    def test_baseline_eta_known_values(self):
        # remaining 4 km at 24 km/h = 10 minutes
        result = baseline_eta(self.vehicle, self.stop)
        self.assertIsNotNone(result)
        eta, remaining = result
        self.assertEqual(remaining, 4.0)
        self.assertEqual(eta, 10.0)

    def test_passed_stop_excluded(self):
        self.vehicle.distance_covered_km = 7.0
        self.assertIsNone(baseline_eta(self.vehicle, self.stop))

    def test_stopped_vehicle_no_eta(self):
        self.vehicle.speed_kmph = 0
        self.assertIsNone(baseline_eta(self.vehicle, self.stop))


class JourneyPlannerTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Journey Org")
        self.user = User.objects.create_user(email="j@test.com", password="Password@1")
        Membership.objects.create(user=self.user, organisation=self.org, role="commuter")
        self.route1 = Route.objects.create(organisation=self.org, name="J1", start_point="A", end_point="C", total_distance_km=12.5)
        self.route2 = Route.objects.create(organisation=self.org, name="J2", start_point="A", end_point="D", total_distance_km=9.0)
        # Shared transfer stop name "Chaheru" on both routes
        self.a1 = Stop.objects.create(route=self.route1, name="Gate", order=1, distance_from_start_km=0, latitude=31.255, longitude=75.705)
        self.b1 = Stop.objects.create(route=self.route1, name="Chaheru", order=2, distance_from_start_km=4.0, latitude=31.240, longitude=75.730)
        self.c1 = Stop.objects.create(route=self.route1, name="City", order=3, distance_from_start_km=12.5, latitude=31.200, longitude=75.790)
        self.a2 = Stop.objects.create(route=self.route2, name="Gate", order=1, distance_from_start_km=0, latitude=31.255, longitude=75.705)
        self.b2 = Stop.objects.create(route=self.route2, name="Chaheru", order=2, distance_from_start_km=3.5, latitude=31.240, longitude=75.730)
        self.d2 = Stop.objects.create(route=self.route2, name="Station", order=3, distance_from_start_km=9.0, latitude=31.223, longitude=75.768)

    def _auth(self):
        r = self.client.post("/api/v1/auth/login/", {"email": "j@test.com", "password": "Password@1"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_direct_route_found(self):
        self._auth()
        r = self.client.get(f"/api/v1/journey/plan/?from_stop={self.a1.id}&to_stop={self.c1.id}")
        self.assertEqual(r.status_code, 200)
        options = r.data["options"]
        self.assertTrue(len(options) >= 1)
        self.assertEqual(options[0]["transfers"], 0)

    def test_transfer_route_found(self):
        self._auth()
        # Gate (route1) -> Station (route2): must transfer at Chaheru
        r = self.client.get(f"/api/v1/journey/plan/?from_stop={self.a1.id}&to_stop={self.d2.id}")
        self.assertEqual(r.status_code, 200)
        options = r.data["options"]
        self.assertTrue(len(options) >= 1)
        self.assertEqual(options[0]["transfers"], 1)
        self.assertEqual(len(options[0]["legs"]), 2)
