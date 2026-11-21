from django.core import mail
from rest_framework.test import APITestCase
from core.models import AuditLog, Organisation, User, Membership
from fleet.models import Route, Vehicle


class AuthTests(APITestCase):
    def test_register_login_me(self):
        r = self.client.post("/api/v1/auth/register/",
                             {"email": "new@test.com", "password": "Password@1", "full_name": "New User"}, format="json")
        self.assertEqual(r.status_code, 201)
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "new@test.com", "password": "Password@1"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        r = self.client.get("/api/v1/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["email"], "new@test.com")

    def test_login_bad_password(self):
        User.objects.create_user(email="a@test.com", password="Password@1")
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "a@test.com", "password": "wrong-password"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_org_register_creates_admin(self):
        r = self.client.post("/api/v1/organisations/register/", {
            "name": "Test Org", "type": "university", "city": "Phagwara",
            "email": "org@test.com", "phone": "123",
            "admin_name": "Org Admin", "admin_email": "admin@testorg.com", "admin_password": "Admin@12345",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Membership.objects.filter(role="org_admin").exists())


class TenantIsolationTests(APITestCase):
    def setUp(self):
        self.org1 = Organisation.objects.create(name="Org One")
        self.org2 = Organisation.objects.create(name="Org Two")
        self.route1 = Route.objects.create(organisation=self.org1, name="R1", start_point="A", end_point="B", total_distance_km=10)
        self.route2 = Route.objects.create(organisation=self.org2, name="R2", start_point="C", end_point="D", total_distance_km=8)
        self.vehicle1 = Vehicle.objects.create(organisation=self.org1, registration_number="ORG1-001", capacity=40)
        self.vehicle2 = Vehicle.objects.create(organisation=self.org2, registration_number="ORG2-001", capacity=40)
        self.user2 = User.objects.create_user(email="u2@test.com", password="Password@1")
        Membership.objects.create(user=self.user2, organisation=self.org2, role="commuter")
        self.user1 = User.objects.create_user(email="u1@test.com", password="Password@1")
        Membership.objects.create(user=self.user1, organisation=self.org1, role="commuter")

    def _auth(self, user):
        r = self.client.post("/api/v1/auth/login/",
                             {"email": user.email, "password": "Password@1"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_org2_user_cannot_see_org1_routes(self):
        self._auth(self.user2)
        r = self.client.get("/api/v1/routes/")
        names = [x["name"] for x in r.data["results"]]
        self.assertIn("R2", names)
        self.assertNotIn("R1", names)

    def test_org2_user_get_org1_route_404(self):
        self._auth(self.user2)
        r = self.client.get(f"/api/v1/routes/{self.route1.id}/")
        self.assertEqual(r.status_code, 404)

    def test_org2_user_cannot_see_org1_vehicles(self):
        self._auth(self.user2)
        r = self.client.get("/api/v1/vehicles/")
        regs = [x["registration_number"] for x in r.data["results"]]
        self.assertIn("ORG2-001", regs)
        self.assertNotIn("ORG1-001", regs)

    def test_commuter_sees_only_own_org_live(self):
        self._auth(self.user1)
        r = self.client.get("/api/v1/live/vehicles/")
        regs = [x["registration_number"] for x in r.data]
        self.assertIn("ORG1-001", regs)
        self.assertNotIn("ORG2-001", regs)

    def test_platform_admin_sees_all(self):
        admin = User.objects.create_user(email="root@test.com", password="Password@1",
                                         is_platform_admin=True)
        self._auth(admin)
        r = self.client.get("/api/v1/routes/")
        self.assertEqual(len(r.data["results"]), 2)


class PasswordResetTests(APITestCase):
    """Wave 2: password-reset request + confirm flow (console/locmem email).

    Django forces DEBUG=False in tests, so uid/token are parsed from the
    emailed body (the DEBUG-only response echo is exercised manually).
    """

    def setUp(self):
        mail.outbox = []
        self.user = User.objects.create_user(email="reset@test.com", password="OldPass@123")

    def _request_reset(self):
        import re

        r = self.client.post("/api/v1/auth/password-reset/", {"email": "reset@test.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        uid = re.search(r"uid: (\S+)", body).group(1)
        token = re.search(r"token: (\S+)", body).group(1)
        return uid, token

    def test_full_reset_flow(self):
        uid, token = self._request_reset()
        self.assertIn("reset", mail.outbox[0].subject.lower())
        self.assertIn(uid, mail.outbox[0].body)
        r = self.client.post("/api/v1/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "NewPass@456",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        # Old password no longer works; new one does.
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "reset@test.com", "password": "OldPass@123"}, format="json")
        self.assertEqual(r.status_code, 401)
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "reset@test.com", "password": "NewPass@456"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)

    def test_unknown_email_still_200_no_enumeration(self):
        r = self.client.post("/api/v1/auth/password-reset/", {"email": "nobody@test.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn("token", r.data)

    def test_missing_email_400(self):
        r = self.client.post("/api/v1/auth/password-reset/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_invalid_token_400(self):
        uid, _token = self._request_reset()
        r = self.client.post("/api/v1/auth/password-reset/confirm/", {
            "uid": uid, "token": "invalid-token", "new_password": "NewPass@456",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_short_password_400(self):
        uid, token = self._request_reset()
        r = self.client.post("/api/v1/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "short",
        }, format="json")
        self.assertEqual(r.status_code, 400)


class OrgRegistrationAuditTests(APITestCase):
    def test_org_registration_writes_audit(self):
        r = self.client.post("/api/v1/organisations/register/", {
            "name": "Audit Reg Org", "type": "university", "city": "Phagwara",
            "email": "org@test.com", "phone": "123",
            "admin_name": "Org Admin", "admin_email": "auditreg@testorg.com", "admin_password": "Admin@12345",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(AuditLog.objects.filter(action="org_registered").exists())
