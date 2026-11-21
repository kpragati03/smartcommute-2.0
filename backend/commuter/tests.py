"""Wave-2 commuter tests: pass QR endpoint + reverse-direction journeys."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from commuter.models import PassApplication, TransportPass
from commuter.services import plan_journey_bidirectional
from core.models import AuditLog, Membership, Organisation, User
from fleet.models import Route, Stop, Vehicle


class PassQRTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="QR Org")
        self.admin = User.objects.create_user(email="qadmin@test.com", password="Password@1")
        Membership.objects.create(user=self.admin, organisation=self.org, role="org_admin")
        self.owner = User.objects.create_user(email="qowner@test.com", password="Password@1")
        Membership.objects.create(user=self.owner, organisation=self.org, role="commuter")
        self.stranger = User.objects.create_user(email="qstranger@test.com", password="Password@1")
        Membership.objects.create(user=self.stranger, organisation=self.org, role="commuter")
        now = timezone.now()
        self.transport_pass = TransportPass.objects.create(
            user=self.owner, organisation=self.org,
            valid_from=now, valid_until=now + timedelta(days=30),
        )

    def _auth(self, user):
        r = self.client.post(
            "/api/v1/auth/login/", {"email": user.email, "password": "Password@1"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_owner_gets_png_qr(self):
        self._auth(self.owner)
        r = self.client.get(f"/api/v1/passes/{self.transport_pass.id}/qr/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_org_admin_gets_png_qr(self):
        self._auth(self.admin)
        r = self.client.get(f"/api/v1/passes/{self.transport_pass.id}/qr/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")

    def test_other_commuter_gets_404(self):
        self._auth(self.stranger)
        r = self.client.get(f"/api/v1/passes/{self.transport_pass.id}/qr/")
        self.assertEqual(r.status_code, 404)

    def test_unauthenticated_gets_401(self):
        r = self.client.get(f"/api/v1/passes/{self.transport_pass.id}/qr/")
        self.assertEqual(r.status_code, 401)

    def test_verify_endpoint_still_works(self):
        self._auth(self.owner)
        r = self.client.get(f"/api/v1/passes/verify/?token={self.transport_pass.qr_token}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["valid"])

    def test_pass_approve_writes_audit(self):
        app = PassApplication.objects.create(user=self.owner, organisation=self.org, reason="Student")
        self._auth(self.admin)
        r = self.client.post(f"/api/v1/passes/applications/{app.id}/approve/", {}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(AuditLog.objects.filter(action="pass_approved").exists())


class ReverseJourneyTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Reverse Org")
        self.user = User.objects.create_user(email="rev@test.com", password="Password@1")
        Membership.objects.create(user=self.user, organisation=self.org, role="commuter")
        self.route1 = Route.objects.create(
            organisation=self.org, name="RJ1", start_point="A", end_point="C", total_distance_km=12.5
        )
        self.route2 = Route.objects.create(
            organisation=self.org, name="RJ2", start_point="A", end_point="D", total_distance_km=9.0
        )
        self.a1 = Stop.objects.create(route=self.route1, name="Gate", order=1, distance_from_start_km=0,
                                      latitude=31.255, longitude=75.705)
        self.b1 = Stop.objects.create(route=self.route1, name="Chaheru", order=2, distance_from_start_km=4.0,
                                      latitude=31.240, longitude=75.730)
        self.c1 = Stop.objects.create(route=self.route1, name="City", order=3, distance_from_start_km=12.5,
                                      latitude=31.200, longitude=75.790)
        self.a2 = Stop.objects.create(route=self.route2, name="Gate", order=1, distance_from_start_km=0,
                                      latitude=31.255, longitude=75.705)
        self.b2 = Stop.objects.create(route=self.route2, name="Chaheru", order=2, distance_from_start_km=3.5,
                                      latitude=31.240, longitude=75.730)
        self.d2 = Stop.objects.create(route=self.route2, name="Station", order=3, distance_from_start_km=9.0,
                                      latitude=31.223, longitude=75.768)

    def _auth(self):
        r = self.client.post("/api/v1/auth/login/", {"email": "rev@test.com", "password": "Password@1"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data["access"]}")

    def test_reverse_direct_journey_found(self):
        self._auth()
        # City (order 3) -> Gate (order 1): reverse direction on the same route
        r = self.client.get(f"/api/v1/journey/plan/?from_stop={self.c1.id}&to_stop={self.a1.id}")
        self.assertEqual(r.status_code, 200)
        options = r.data["options"]
        self.assertTrue(len(options) >= 1)
        self.assertEqual(options[0]["transfers"], 0)
        leg = options[0]["legs"][0]
        self.assertEqual(leg["from_stop_id"], self.c1.id)
        self.assertEqual(leg["to_stop_id"], self.a1.id)
        # 12.5 km at fallback 25 km/h = 30 minutes (uses |distance difference|)
        self.assertEqual(leg["duration_minutes"], 30.0)

    def test_forward_direct_still_found(self):
        self._auth()
        r = self.client.get(f"/api/v1/journey/plan/?from_stop={self.a1.id}&to_stop={self.c1.id}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data["options"]) >= 1)
        self.assertEqual(r.data["options"][0]["transfers"], 0)

    def test_reverse_transfer_journey_found(self):
        self._auth()
        # Station (route2 order 3) -> City (route1 order 3) via Chaheru, both legs reverse-capable
        r = self.client.get(f"/api/v1/journey/plan/?from_stop={self.d2.id}&to_stop={self.c1.id}")
        self.assertEqual(r.status_code, 200)
        options = r.data["options"]
        self.assertTrue(len(options) >= 1)
        self.assertEqual(options[0]["transfers"], 1)

    def test_service_reverse_direct(self):
        options = plan_journey_bidirectional(self.c1.id, self.a1.id, [self.org.id])
        self.assertTrue(len(options) >= 1)
        self.assertEqual(options[0]["transfers"], 0)
