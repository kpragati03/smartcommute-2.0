import json
import math
from django.db.models import Avg, Count
from django.db.models.functions import ExtractHour
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import user_org_ids, is_org_admin
from fleet.models import Vehicle, Trip, Route, Device
from tracking.models import OccupancyRecord, ETAPrediction
from commuter.models import Complaint
from . import training as training_mod
from .services import predict_crowd


def _org_qs(request, qs, field="organisation"):
    org_ids = user_org_ids(request.user)
    if org_ids is not None:
        qs = qs.filter(**{f"{field}__in": org_ids})
    return qs


class AnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        vehicles = _org_qs(request, Vehicle.objects.all())
        trips = _org_qs(request, Trip.objects.all(), "route__organisation")
        today = timezone.localdate()
        occ_today = OccupancyRecord.objects.filter(recorded_at__date=today)
        org_ids = user_org_ids(request.user)
        if org_ids is not None:
            occ_today = occ_today.filter(vehicle__organisation__in=org_ids)
        total_pax_today = sum(occ_today.values_list("passengers_onboard", flat=True))
        avg_occ = vehicles.aggregate(a=Avg("passengers_onboard"))["a"] or 0
        avg_cap = vehicles.aggregate(a=Avg("capacity"))["a"] or 1
        devices = _org_qs(request, Device.objects.all(), "vehicle__organisation")
        cutoff = timezone.now() - timezone.timedelta(minutes=5)
        online = devices.filter(last_seen__gte=cutoff).count()
        complaints = _org_qs(request, Complaint.objects.filter(status="open"))
        return Response({
            "total_vehicles": vehicles.count(),
            "active_vehicles": vehicles.filter(status="active").count(),
            "running_trips": trips.filter(status="running").count(),
            "delayed_trips": trips.filter(status="delayed").count(),
            "avg_occupancy_percent": round((avg_occ / avg_cap) * 100, 1) if avg_cap else 0,
            "total_passengers_today": total_pax_today,
            "open_complaints": complaints.count(),
            "devices_online": online,
            "devices_offline": devices.count() - online,
        })


class AnalyticsRoutesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        routes = _org_qs(request, Route.objects.all())
        out = []
        for r in routes:
            trips = r.trips.all()
            out.append({
                "route_id": r.id, "route_name": r.name, "trips": trips.count(),
                "avg_delay_minutes": round(trips.aggregate(a=Avg("delay_minutes"))["a"] or 0, 1),
                "avg_occupancy": round(Vehicle.objects.filter(current_route=r).aggregate(a=Avg("passengers_onboard"))["a"] or 0, 1),
                "passengers": OccupancyRecord.objects.filter(vehicle__current_route=r).count(),
            })
        return Response(out)


class AnalyticsCrowdView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        qs = OccupancyRecord.objects.annotate(hour=ExtractHour("recorded_at"))
        org_ids = user_org_ids(request.user)
        if org_ids is not None:
            qs = qs.filter(vehicle__organisation__in=org_ids)
        rows = qs.values("hour").annotate(avg_passengers=Avg("passengers_onboard"), samples=Count("id")).order_by("hour")
        return Response([{"hour": r["hour"], "avg_passengers": round(r["avg_passengers"] or 0, 1),
                          "samples": r["samples"]} for r in rows])


class AnalyticsETAAccuracyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        result = {}
        for method in ("baseline", "ml"):
            preds = ETAPrediction.objects.filter(method=method, actual_eta_minutes__isnull=False)
            org_ids = user_org_ids(request.user)
            if org_ids is not None:
                preds = preds.filter(vehicle__organisation__in=org_ids)
            errors = [abs(p.predicted_eta_minutes - p.actual_eta_minutes) for p in preds]
            if errors:
                mae = sum(errors) / len(errors)
                rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
                result[method] = {"mae": round(mae, 2), "rmse": round(rmse, 2), "n": len(errors)}
            else:
                result[method] = {"mae": None, "rmse": None, "n": 0}
        return Response(result)


# ---------------------------------------------------------------------------
# Phase 10 additions: crowd prediction + trained-model metrics
# ---------------------------------------------------------------------------

class CrowdPredictionView(APIView):
    """GET /intelligence/crowd-prediction/?route_id=&hour= (JWT, org-scoped)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        route_id = request.query_params.get("route_id")
        hour_raw = request.query_params.get("hour")
        if route_id is None or hour_raw is None:
            return Response({"detail": "route_id and hour are required"}, status=400)
        try:
            route_id, hour = int(route_id), int(hour_raw)
        except ValueError:
            return Response({"detail": "route_id and hour must be integers"}, status=400)
        if not 0 <= hour <= 23:
            return Response({"detail": "hour must be between 0 and 23"}, status=400)
        try:
            route = Route.objects.get(pk=route_id)
        except Route.DoesNotExist:
            return Response({"detail": "Route not found"}, status=404)
        org_ids = user_org_ids(request.user)
        if org_ids is not None and route.organisation_id not in org_ids:
            return Response({"detail": "Route not found"}, status=404)
        result = predict_crowd(route, hour)
        result.update({"route_id": route.id, "hour": hour})
        return Response(result)


class ETAModelMetricsView(APIView):
    """GET /intelligence/eta-metrics/ — training metrics JSON of the saved model."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        path = training_mod.DEFAULT_METRICS_PATH
        if not path.exists():
            return Response({"detail": "No trained model metrics yet. "
                                       "Run: python manage.py train_eta_model"}, status=404)
        try:
            return Response(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return Response({"detail": "Metrics file unreadable"}, status=500)
