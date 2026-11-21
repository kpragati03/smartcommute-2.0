from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import user_org_ids
from fleet.models import Vehicle, Stop
from .services import baseline_eta, eta_for_vehicle_stop, plan_journey
from .models import ETAPrediction


class LiveVehiclesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Vehicle.objects.select_related("current_route").all()
        org_ids = user_org_ids(request.user)
        if org_ids is not None:
            qs = qs.filter(organisation__in=org_ids)
        now = timezone.now()
        out = []
        for v in qs:
            is_stale = True
            if v.last_updated:
                is_stale = (now - v.last_updated).total_seconds() > 60
            out.append({
                "id": v.id, "registration_number": v.registration_number,
                "route_id": v.current_route_id,
                "route_name": v.current_route.name if v.current_route else None,
                "latitude": v.current_latitude, "longitude": v.current_longitude,
                "distance_covered_km": v.distance_covered_km, "speed_kmph": v.speed_kmph,
                "passengers_onboard": v.passengers_onboard, "capacity": v.capacity,
                "seats_available": v.seats_available, "occupancy_percent": v.occupancy_percent,
                "crowd_level": v.crowd_level,
                "last_updated": v.last_updated.isoformat() if v.last_updated else None,
                "is_stale": is_stale, "status": v.status,
            })
        return Response(out)


class LiveETAView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stop_id = request.query_params.get("stop_id")
        if not stop_id:
            return Response({"detail": "stop_id is required"}, status=400)
        try:
            stop = Stop.objects.select_related("route").get(pk=stop_id)
        except Stop.DoesNotExist:
            return Response({"detail": "Stop not found"}, status=404)
        org_ids = user_org_ids(request.user)
        if org_ids is not None and stop.route.organisation_id not in org_ids:
            return Response({"detail": "Stop not found"}, status=404)
        vehicles = Vehicle.objects.filter(current_route_id=stop.route_id, status="active")
        out = []
        for v in vehicles:
            # Phase 10: ML-first ETA hook (falls back to baseline_eta inside).
            result = eta_for_vehicle_stop(v, stop)
            if result is None:
                continue
            eta, remaining, method = result
            ETAPrediction.objects.create(vehicle=v, stop=stop, predicted_eta_minutes=eta, method=method)
            out.append({"vehicle_id": v.id, "registration_number": v.registration_number,
                        "eta_minutes": eta, "method": method, "distance_remaining_km": remaining})
        out.sort(key=lambda x: x["eta_minutes"])
        return Response(out)


class JourneyPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from_stop = request.query_params.get("from_stop")
        to_stop = request.query_params.get("to_stop")
        if not from_stop or not to_stop:
            return Response({"detail": "from_stop and to_stop are required"}, status=400)
        try:
            from_id, to_id = int(from_stop), int(to_stop)
        except ValueError:
            return Response({"detail": "from_stop and to_stop must be integers"}, status=400)
        options = plan_journey(from_id, to_id, user_org_ids(request.user))
        return Response({"options": options})
