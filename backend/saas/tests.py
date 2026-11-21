"""Wave-2 SaaS tests: subscription upgrade writes an audit entry."""
from rest_framework.test import APITestCase

from core.models import AuditLog, Membership, Organisation, User
from saas.models import SubscriptionPlan


class SubscriptionAuditTests(APITestCase):
    def test_upgrade_writes_audit(self):
        org = Organisation.objects.create(name="SaaS Audit Org")
        plan = SubscriptionPlan.objects.create(name="GrowthTest", max_vehicles=25, price_monthly=2999)
        admin = User.objects.create_user(email="saas@test.com", password="Password@1")
        Membership.objects.create(user=admin, organisation=org, role="org_admin")
        r = self.client.post("/api/v1/auth/login/", {"email": "saas@test.com", "password": "Password@1"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        r = self.client.post("/api/v1/subscription/upgrade/", {"plan_id": plan.id}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="subscription_upgraded", organisation=org).exists())
