"""Wave-2 fleet tests: telemetry throttling + audit-log writes."""
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.settings import api_settings
from rest_framework.test import APITestCase

from core.models import AuditLog, Membership, Organisation, User
from fleet.models import Device, Driver, Route, Trip, Vehicle, hash_device_key


class TelemetryThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.org = Organisation.objects.create(name="Throttle Org")
        self.route = Route.objects.create(
            organisation=self.org, name="THR", start_point="A", end_point="B", total_distance_km=10
        )
        self.vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="THR-001", capacity=40, current_route=self.route
        )
        self.raw_key = "throttle-test-key-xyz"
        Device.objects.create(vehicle=self.vehicle, device_key_hash=hash_device_key(self.raw_key))

    def tearDown(self):
        cache.clear()

    def _payload(self):
        return {"latitude": 31.25, "longitude": 75.70, "distance_covered_km": 1.0,
                "speed_kmph": 20.0, "passengers_onboard": 5}

    @override_settings(REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
        "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
        "PAGE_SIZE": 20,
        "DEFAULT_THROTTLE_RATES": {"telemetry": "3/min"},
    })
    def test_telemetry_throttled_after_limit(self):
        # DRF caches api_settings; reload so the override rate applies.
        api_settings.reload()
        try:
            for _ in range(3):
                r = self.client.post("/api/v1/devices/telemetry/", self._payload(),
                                     format="json", HTTP_X_DEVICE_KEY=self.raw_key)
                self.assertEqual(r.status_code, 201)
            r = self.client.post("/api/v1/devices/telemetry/", self._payload(),
                                 format="json", HTTP_X_DEVICE_KEY=self.raw_key)
            self.assertEqual(r.status_code, 429)
        finally:
            api_settings.reload()
            cache.clear()

    def test_throttle_is_per_device(self):
        """A different device key has its own budget (keyed by key hash)."""
        other_vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="THR-002", capacity=40, current_route=self.route
        )
        other_key = "throttle-other-key-abc"
        Device.objects.create(vehicle=other_vehicle, device_key_hash=hash_device_key(other_key))
        r = self.client.post("/api/v1/devices/telemetry/", self._payload(),
                             format="json", HTTP_X_DEVICE_KEY=other_key)
        self.assertEqual(r.status_code, 201)


class AuditLogFleetTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Audit Org")
        self.route = Route.objects.create(
            organisation=self.org, name="AR", start_point="A", end_point="B", total_distance_km=10
        )
        self.admin = User.objects.create_user(email="aadmin@test.com", password="Password@1")
        Membership.objects.create(user=self.admin, organisation=self.org, role="org_admin")
        self.driver_user = User.objects.create_user(email="adriver@test.com", password="Password@1")
        Membership.objects.create(user=self.driver_user, organisation=self.org, role="driver")
        self.driver = Driver.objects.create(user=self.driver_user, organisation=self.org)

    def _auth(self, user):
        r = self.client.post(
            "/api/v1/auth/login/", {"email": user.email, "password": "Password@1"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_vehicle_create_and_delete_write_audit(self):
        self._auth(self.admin)
        r = self.client.post("/api/v1/vehicles/", {
            "organisation": self.org.id, "registration_number": "AUD-001", "capacity": 40, "status": "active",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        vid = r.data["id"]
        self.assertTrue(AuditLog.objects.filter(action="vehicle_created", object_id=str(vid)).exists())
        r = self.client.delete(f"/api/v1/vehicles/{vid}/")
        self.assertEqual(r.status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action="vehicle_deleted", object_id=str(vid)).exists())

    def test_device_create_writes_audit(self):
        vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="AUD-002", capacity=40, current_route=self.route
        )
        self._auth(self.admin)
        r = self.client.post("/api/v1/devices/", {"vehicle": vehicle.id}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("device_key", r.data)
        self.assertTrue(AuditLog.objects.filter(action="device_created").exists())

    def test_trip_start_end_write_audit(self):
        vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="AUD-003", capacity=40, current_route=self.route
        )
        trip = Trip.objects.create(
            route=self.route, vehicle=vehicle, driver=self.driver,
            scheduled_start=timezone.now(), status="scheduled",
        )
        self._auth(self.driver_user)
        r = self.client.post(f"/api/v1/driver/trips/{trip.id}/start/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"/api/v1/driver/trips/{trip.id}/end/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="trip_started", object_id=str(trip.id)).exists())
        self.assertTrue(AuditLog.objects.filter(action="trip_ended", object_id=str(trip.id)).exists())
