from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_audit
from core.permissions import user_org_ids, is_org_admin
from .models import Route, Stop, Vehicle, Driver, Schedule, Trip, Device, hash_device_key, generate_device_key
from .serializers import (RouteSerializer, StopSerializer, VehicleSerializer, DriverSerializer,
                          ScheduleSerializer, TripSerializer, DeviceSerializer)
from .throttles import DeviceTelemetryThrottle


class OrgScopedViewSet(viewsets.ModelViewSet):
    """Base: filter queryset by caller's org memberships; writes need org_admin."""
    org_field = "organisation"

    def get_queryset(self):
        qs = super().get_queryset()
        org_ids = user_org_ids(self.request.user)
        if org_ids is None:
            return qs
        return qs.filter(**{f"{self.org_field}__in": org_ids})

    def _check_write(self, org_id):
        if not is_org_admin(self.request.user, org_id):
            return Response({"detail": "org_admin role required for writes"}, status=403)
        return None

    def create(self, request, *args, **kwargs):
        org_id = request.data.get("organisation")
        # For route-linked resources, org comes from the route
        if org_id is None and request.data.get("route"):
            try:
                org_id = Route.objects.get(pk=request.data["route"]).organisation_id
            except Route.DoesNotExist:
                return Response({"detail": "Route not found"}, status=400)
        if org_id is None and request.data.get("vehicle"):
            try:
                org_id = Vehicle.objects.get(pk=request.data["vehicle"]).organisation_id
            except Vehicle.DoesNotExist:
                return Response({"detail": "Vehicle not found"}, status=400)
        if org_id is not None:
            err = self._check_write(int(org_id))
            if err:
                return err
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        org_id = getattr(obj, "organisation_id", None)
        if org_id is None and hasattr(obj, "route"):
            org_id = obj.route.organisation_id
        if org_id is None and hasattr(obj, "vehicle"):
            org_id = obj.vehicle.organisation_id
        err = self._check_write(org_id)
        if err:
            return err
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        org_id = getattr(obj, "organisation_id", None)
        if org_id is None and hasattr(obj, "route"):
            org_id = obj.route.organisation_id
        err = self._check_write(org_id)
        if err:
            return err
        return super().destroy(request, *args, **kwargs)


class RouteViewSet(OrgScopedViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    org_field = "organisation"


class StopViewSet(OrgScopedViewSet):
    queryset = Stop.objects.select_related("route").all()
    serializer_class = StopSerializer
    org_field = "route__organisation"

    def get_queryset(self):
        qs = super().get_queryset()
        route = self.request.query_params.get("route")
        if route:
            qs = qs.filter(route_id=route)
        return qs


class VehicleViewSet(OrgScopedViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    org_field = "organisation"

    def create(self, request, *args, **kwargs):
        # SaaS plan limit check (wave-1: enforced when subscription exists)
        org_id = request.data.get("organisation")
        if org_id:
            from saas.models import Subscription
            sub = Subscription.objects.filter(organisation_id=org_id).select_related("plan").first()
            if sub and Vehicle.objects.filter(organisation_id=org_id).count() >= sub.plan.max_vehicles:
                return Response(
                    {"detail": f"Plan limit reached: max {sub.plan.max_vehicles} vehicles. Upgrade your plan."},
                    status=400)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        vehicle = serializer.save()
        log_audit(actor=self.request.user, organisation=vehicle.organisation,
                  action="vehicle_created", object_type="Vehicle", object_id=vehicle.id,
                  detail=f"Vehicle {vehicle.registration_number} created")

    def perform_destroy(self, instance):
        org = instance.organisation
        reg, vid = instance.registration_number, instance.id
        instance.delete()
        log_audit(actor=self.request.user, organisation=org,
                  action="vehicle_deleted", object_type="Vehicle", object_id=vid,
                  detail=f"Vehicle {reg} deleted")


class DriverViewSet(OrgScopedViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    org_field = "organisation"


class ScheduleViewSet(OrgScopedViewSet):
    queryset = Schedule.objects.select_related("route").all()
    serializer_class = ScheduleSerializer
    org_field = "route__organisation"


class TripViewSet(OrgScopedViewSet):
    queryset = Trip.objects.select_related("route", "vehicle", "driver").all()
    serializer_class = TripSerializer
    org_field = "route__organisation"


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.select_related("vehicle").all()
    serializer_class = DeviceSerializer
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        qs = super().get_queryset()
        org_ids = user_org_ids(self.request.user)
        if org_ids is None:
            return qs
        return qs.filter(vehicle__organisation__in=org_ids)

    def create(self, request, *args, **kwargs):
        vehicle_id = request.data.get("vehicle")
        if not vehicle_id:
            return Response({"detail": "vehicle is required"}, status=400)
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"detail": "Vehicle not found"}, status=404)
        if not is_org_admin(request.user, vehicle.organisation_id):
            return Response({"detail": "org_admin role required"}, status=403)
        raw_key = generate_device_key()
        device = Device.objects.create(vehicle=vehicle, device_key_hash=hash_device_key(raw_key))
        log_audit(actor=request.user, organisation=vehicle.organisation,
                  action="device_created", object_type="Device", object_id=device.id,
                  detail=f"Device created for vehicle {vehicle.registration_number}")
        data = DeviceSerializer(device).data
        data["device_key"] = raw_key  # returned ONCE
        return Response(data, status=201)


class TelemetryView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DeviceTelemetryThrottle]

    def post(self, request):
        raw_key = request.headers.get("X-Device-Key", "")
        if not raw_key:
            return Response({"detail": "Missing X-Device-Key header"}, status=401)
        device = Device.objects.filter(device_key_hash=hash_device_key(raw_key), is_active=True).select_related("vehicle").first()
        if device is None:
            return Response({"detail": "Invalid device key"}, status=401)
        vehicle = device.vehicle
        d = request.data
        errors = {}
        try:
            lat = float(d["latitude"]); lng = float(d["longitude"])
            dist = float(d["distance_covered_km"]); speed = float(d["speed_kmph"])
            pax = int(d["passengers_onboard"])
        except (KeyError, TypeError, ValueError):
            return Response({"detail": "Required numeric fields: latitude, longitude, distance_covered_km, speed_kmph, passengers_onboard"}, status=400)
        if not (-90 <= lat <= 90):
            errors["latitude"] = "Must be between -90 and 90"
        if not (-180 <= lng <= 180):
            errors["longitude"] = "Must be between -180 and 180"
        if not (0 <= speed <= 200):
            errors["speed_kmph"] = "Must be between 0 and 200"
        if dist < 0:
            errors["distance_covered_km"] = "Must be >= 0"
        if not (0 <= pax <= vehicle.capacity):
            errors["passengers_onboard"] = f"Must be between 0 and capacity ({vehicle.capacity})"
        if errors:
            return Response({"detail": "Validation failed", "errors": errors}, status=400)

        recorded_at = timezone.now()
        if d.get("recorded_at"):
            parsed = parse_datetime(str(d["recorded_at"]))
            if parsed is not None:
                recorded_at = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)

        from tracking.models import LocationHistory, OccupancyRecord
        LocationHistory.objects.create(vehicle=vehicle, latitude=lat, longitude=lng,
                                       distance_covered_km=dist, speed_kmph=speed, recorded_at=recorded_at)
        OccupancyRecord.objects.create(vehicle=vehicle, passengers_onboard=pax, recorded_at=recorded_at)
        vehicle.current_latitude = lat
        vehicle.current_longitude = lng
        vehicle.distance_covered_km = dist
        vehicle.speed_kmph = speed
        vehicle.passengers_onboard = pax
        vehicle.last_updated = recorded_at
        vehicle.save(update_fields=["current_latitude", "current_longitude", "distance_covered_km",
                                    "speed_kmph", "passengers_onboard", "last_updated"])
        device.last_seen = recorded_at
        device.save(update_fields=["last_seen"])
        return Response({"status": "ok"}, status=201)


# ---- Driver endpoints ----

def _driver_profile(user):
    return Driver.objects.filter(user=user).first()


def _trip_payload(trip):
    stops = list(trip.route.stops.order_by("order").values("id", "name", "order", "distance_from_start_km"))
    return {
        "trip": TripSerializer(trip).data,
        "stops": stops,
        "vehicle_distance_covered_km": trip.vehicle.distance_covered_km,
        "passengers_onboard": trip.vehicle.passengers_onboard,
    }


class DriverMyTripView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = _driver_profile(request.user)
        if driver is None:
            return Response({"detail": "No driver profile for this user"}, status=404)
        trip = (Trip.objects.filter(driver=driver, status__in=["running", "delayed"]).order_by("scheduled_start").first()
                or Trip.objects.filter(driver=driver, status="scheduled", scheduled_start__gte=timezone.now()).order_by("scheduled_start").first()
                or Trip.objects.filter(driver=driver, status="scheduled").order_by("-scheduled_start").first())
        if trip is None:
            return Response({"detail": "No assigned trip"}, status=404)
        return Response(_trip_payload(trip))


class DriverTripActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, action):
        driver = _driver_profile(request.user)
        if driver is None:
            return Response({"detail": "No driver profile for this user"}, status=404)
        trip = Trip.objects.filter(pk=pk, driver=driver).first()
        if trip is None:
            return Response({"detail": "Trip not found for this driver"}, status=404)
        if action == "start":
            trip.status = "running"; trip.actual_start = timezone.now()
            trip.vehicle.current_route = trip.route
            trip.vehicle.save(update_fields=["current_route"])
        elif action == "end":
            trip.status = "completed"; trip.actual_end = timezone.now()
        elif action == "delay":
            minutes = request.data.get("minutes", 0)
            trip.status = "delayed"; trip.delay_minutes = int(minutes or 0)
            trip.notes = request.data.get("note", trip.notes)
        elif action == "breakdown":
            trip.status = "delayed"; trip.notes = request.data.get("note", "Breakdown reported")
            trip.vehicle.status = "maintenance"; trip.vehicle.save(update_fields=["status"])
        elif action == "passengers":
            pax = request.data.get("passengers_onboard")
            if pax is None or not (0 <= int(pax) <= trip.vehicle.capacity):
                return Response({"detail": f"passengers_onboard must be 0..{trip.vehicle.capacity}"}, status=400)
            trip.vehicle.passengers_onboard = int(pax)
            trip.vehicle.save(update_fields=["passengers_onboard"])
            from tracking.models import OccupancyRecord
            OccupancyRecord.objects.create(vehicle=trip.vehicle, passengers_onboard=int(pax), recorded_at=timezone.now())
        else:
            return Response({"detail": "Unknown action"}, status=400)
        trip.save()
        # Wave-2: audit + notification triggers (best-effort, never break the action)
        try:
            org_id = trip.route.organisation_id
            if action == "start":
                log_audit(actor=request.user, organisation=trip.route.organisation,
                          action="trip_started", object_type="Trip", object_id=trip.id,
                          detail=f"Trip {trip.id} on {trip.route.name} started")
                from notifications.services import notify_route_favouriters
                notify_route_favouriters(
                    trip.route_id, "trip",
                    f"Trip started on {trip.route.name}",
                    f"Vehicle {trip.vehicle.registration_number} has started its trip on "
                    f"{trip.route.name} ({trip.route.start_point} → {trip.route.end_point}).",
                )
            elif action == "end":
                log_audit(actor=request.user, organisation=trip.route.organisation,
                          action="trip_ended", object_type="Trip", object_id=trip.id,
                          detail=f"Trip {trip.id} on {trip.route.name} ended")
            elif action == "delay":
                from notifications.services import notify_org_commuters
                notify_org_commuters(
                    org_id, "delay",
                    f"Delay on {trip.route.name}",
                    f"Vehicle {trip.vehicle.registration_number} on {trip.route.name} is delayed "
                    f"by {trip.delay_minutes} minutes. {trip.notes}".strip(),
                )
            elif action == "breakdown":
                from notifications.services import notify_org_admins, notify_org_commuters
                body = (f"Vehicle {trip.vehicle.registration_number} on {trip.route.name} "
                        f"has reported a breakdown. {trip.notes}").strip()
                notify_org_commuters(org_id, "breakdown", f"Breakdown on {trip.route.name}", body)
                notify_org_admins(org_id, "breakdown", f"Breakdown reported: {trip.vehicle.registration_number}", body)
        except Exception:
            pass
        return Response(TripSerializer(trip).data)


class DriverHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = _driver_profile(request.user)
        if driver is None:
            return Response({"detail": "No driver profile for this user"}, status=404)
        trips = Trip.objects.filter(driver=driver, status__in=["completed", "cancelled"]).order_by("-scheduled_start")[:50]
        return Response(TripSerializer(trips, many=True).data)
