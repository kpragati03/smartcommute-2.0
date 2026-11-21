"""Wave-2 notification trigger tests."""
from django.utils import timezone
from rest_framework.test import APITestCase

from commuter.models import FavouriteRoute, PassApplication, Complaint
from core.models import Membership, Organisation, User
from fleet.models import Driver, Route, Trip, Vehicle
from notifications.models import Notification


class NotificationTriggerTests(APITestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Notify Org")
        self.route = Route.objects.create(
            organisation=self.org, name="NR", start_point="A", end_point="B", total_distance_km=10
        )
        self.vehicle = Vehicle.objects.create(
            organisation=self.org, registration_number="NOT-001", capacity=40, current_route=self.route
        )
        self.admin = User.objects.create_user(email="nadmin@test.com", password="Password@1")
        Membership.objects.create(user=self.admin, organisation=self.org, role="org_admin")
        self.driver_user = User.objects.create_user(email="ndriver@test.com", password="Password@1")
        Membership.objects.create(user=self.driver_user, organisation=self.org, role="driver")
        self.driver = Driver.objects.create(user=self.driver_user, organisation=self.org)
        self.commuter = User.objects.create_user(email="ncomm@test.com", password="Password@1")
        Membership.objects.create(user=self.commuter, organisation=self.org, role="commuter")
        self.trip = Trip.objects.create(
            route=self.route, vehicle=self.vehicle, driver=self.driver,
            scheduled_start=timezone.now(), status="scheduled",
        )

    def _auth(self, user):
        r = self.client.post(
            "/api/v1/auth/login/", {"email": user.email, "password": "Password@1"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_delay_notifies_org_commuters(self):
        self._auth(self.driver_user)
        r = self.client.post(
            f"/api/v1/driver/trips/{self.trip.id}/delay/", {"minutes": 15, "note": "Traffic"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        notes = Notification.objects.filter(user=self.commuter, type="delay")
        self.assertEqual(notes.count(), 1)
        self.assertIn("Delay", notes.first().title)
        # Admin does not get delay notifications (commuters only)
        self.assertEqual(Notification.objects.filter(user=self.admin, type="delay").count(), 0)

    def test_breakdown_notifies_commuters_and_admins(self):
        self._auth(self.driver_user)
        r = self.client.post(
            f"/api/v1/driver/trips/{self.trip.id}/breakdown/", {"note": "Engine fault"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.commuter, type="breakdown").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.admin, type="breakdown").count(), 1)

    def test_trip_start_notifies_route_favouriters_only(self):
        other = User.objects.create_user(email="nother@test.com", password="Password@1")
        Membership.objects.create(user=other, organisation=self.org, role="commuter")
        FavouriteRoute.objects.create(user=self.commuter, route=self.route)
        self._auth(self.driver_user)
        r = self.client.post(f"/api/v1/driver/trips/{self.trip.id}/start/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.commuter, type="trip").count(), 1)
        self.assertEqual(Notification.objects.filter(user=other, type="trip").count(), 0)

    def test_pass_approval_notifies_applicant(self):
        app = PassApplication.objects.create(user=self.commuter, organisation=self.org, reason="Student")
        self._auth(self.admin)
        r = self.client.post(f"/api/v1/passes/applications/{app.id}/approve/", {}, format="json")
        self.assertEqual(r.status_code, 201)
        notes = Notification.objects.filter(user=self.commuter, type="pass")
        self.assertEqual(notes.count(), 1)
        self.assertIn("approved", notes.first().title.lower())

    def test_pass_rejection_notifies_applicant(self):
        app = PassApplication.objects.create(user=self.commuter, organisation=self.org, reason="Student")
        self._auth(self.admin)
        r = self.client.post(f"/api/v1/passes/applications/{app.id}/reject/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        notes = Notification.objects.filter(user=self.commuter, type="pass")
        self.assertEqual(notes.count(), 1)
        self.assertIn("rejected", notes.first().title.lower())

    def test_incident_notifies_org_admins(self):
        self._auth(self.commuter)
        r = self.client.post(
            "/api/v1/incidents/", {"type": "accident", "description": "Minor scrape"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Notification.objects.filter(user=self.admin, type="incident").count(), 1)

    def test_complaint_status_change_notifies_reporter(self):
        complaint = Complaint.objects.create(
            user=self.commuter, organisation=self.org, category="wrong_eta", description="ETA off"
        )
        self._auth(self.admin)
        r = self.client.patch(f"/api/v1/complaints/{complaint.id}/", {"status": "resolved"}, format="json")
        self.assertEqual(r.status_code, 200)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, "resolved")
        self.assertEqual(Notification.objects.filter(user=self.commuter, type="complaint").count(), 1)

    def test_notify_helper_creates_typed_notification(self):
        from notifications.services import notify

        note = notify(self.commuter, "general", "Hello", "Body text")
        self.assertIsNotNone(note)
        self.assertEqual(note.type, "general")
        self.assertEqual(note.message, "Body text")
