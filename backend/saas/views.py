from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.audit import log_audit
from core.permissions import is_org_admin
from .models import SubscriptionPlan, Subscription, Invoice


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["id", "name", "max_vehicles", "price_monthly", "features"]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "organisation", "plan", "status", "start_date", "end_date"]


class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PlanSerializer(SubscriptionPlan.objects.all(), many=True).data)


def _user_org(request):
    m = request.user.memberships.filter(role="org_admin").first() or request.user.memberships.first()
    return m.organisation if m else None


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        org = _user_org(request)
        if org is None:
            return Response({"detail": "No organisation"}, status=404)
        sub = Subscription.objects.filter(organisation=org).select_related("plan").first()
        if sub is None:
            return Response({"detail": "No subscription"}, status=404)
        return Response(SubscriptionSerializer(sub).data)


class SubscriptionUpgradeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        org = _user_org(request)
        plan = SubscriptionPlan.objects.filter(pk=request.data.get("plan_id")).first()
        if plan is None:
            return Response({"detail": "Plan not found"}, status=404)
        sub, _ = Subscription.objects.update_or_create(
            organisation=org, defaults={"plan": plan, "status": "active"})
        invoice = Invoice.objects.create(organisation=org, subscription=sub,
                                         amount=plan.price_monthly, status="pending")
        log_audit(actor=request.user, organisation=org,
                  action="subscription_upgraded", object_type="Subscription", object_id=sub.id,
                  detail=f"Subscription upgraded to plan '{plan.name}' (invoice {invoice.id})")
        data = SubscriptionSerializer(sub).data
        data["invoice_id"] = invoice.id
        data["invoice_status"] = invoice.status
        return Response(data)
