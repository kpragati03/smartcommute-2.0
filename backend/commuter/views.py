import io
from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_audit
from core.permissions import user_org_ids, is_org_admin
from fleet.models import Route, Stop
from .models import (FavouriteRoute, FavouriteStop, SavedJourney, PassApplication,
                     TransportPass, Complaint, Feedback, Incident)
from .serializers import (FavouriteRouteSerializer, FavouriteStopSerializer, SavedJourneySerializer,
                          PassApplicationSerializer, TransportPassSerializer, ComplaintSerializer,
                          FeedbackSerializer, IncidentSerializer)
from .services import plan_journey_bidirectional


def _org_of_user(user):
    m = user.memberships.first()
    return m.organisation if m else None


class FavouriteRouteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favs = FavouriteRoute.objects.filter(user=request.user).select_related("route")
        return Response(FavouriteRouteSerializer(favs, many=True).data)

    def post(self, request):
        route_id = request.data.get("route")
        if not route_id:
            return Response({"detail": "route is required"}, status=400)
        route = Route.objects.filter(pk=route_id).first()
        org_ids = user_org_ids(request.user)
        if route is None or (org_ids is not None and route.organisation_id not in org_ids):
            return Response({"detail": "Route not found"}, status=404)
        fav, _ = FavouriteRoute.objects.get_or_create(user=request.user, route=route)
        return Response(FavouriteRouteSerializer(fav).data, status=201)

    def delete(self, request):
        route_id = request.data.get("route") or request.query_params.get("route")
        deleted, _ = FavouriteRoute.objects.filter(user=request.user, route_id=route_id).delete()
        return Response(status=204) if deleted else Response({"detail": "Not found"}, status=404)


class FavouriteStopView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favs = FavouriteStop.objects.filter(user=request.user).select_related("stop")
        return Response(FavouriteStopSerializer(favs, many=True).data)

    def post(self, request):
        stop_id = request.data.get("stop")
        if not stop_id:
            return Response({"detail": "stop is required"}, status=400)
        stop = Stop.objects.select_related("route").filter(pk=stop_id).first()
        org_ids = user_org_ids(request.user)
        if stop is None or (org_ids is not None and stop.route.organisation_id not in org_ids):
            return Response({"detail": "Stop not found"}, status=404)
        fav, _ = FavouriteStop.objects.get_or_create(user=request.user, stop=stop)
        return Response(FavouriteStopSerializer(fav).data, status=201)

    def delete(self, request):
        stop_id = request.data.get("stop") or request.query_params.get("stop")
        deleted, _ = FavouriteStop.objects.filter(user=request.user, stop_id=stop_id).delete()
        return Response(status=204) if deleted else Response({"detail": "Not found"}, status=404)


class SavedJourneyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        journeys = SavedJourney.objects.filter(user=request.user)
        return Response(SavedJourneySerializer(journeys, many=True).data)

    def post(self, request):
        src = request.data.get("source_stop"); dst = request.data.get("destination_stop")
        if not src or not dst:
            return Response({"detail": "source_stop and destination_stop are required"}, status=400)
        if not Stop.objects.filter(pk__in=[src, dst]).count() == 2:
            return Response({"detail": "Stop not found"}, status=404)
        journey = SavedJourney.objects.create(user=request.user, source_stop_id=src,
                                              destination_stop_id=dst, label=request.data.get("label", ""))
        return Response(SavedJourneySerializer(journey).data, status=201)

    def delete(self, request):
        jid = request.data.get("id") or request.query_params.get("id")
        deleted, _ = SavedJourney.objects.filter(user=request.user, pk=jid).delete()
        return Response(status=204) if deleted else Response({"detail": "Not found"}, status=404)


class PassApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org = _org_of_user(request.user)
        if org is None:
            return Response({"detail": "User has no organisation membership"}, status=400)
        reason = request.data.get("reason", "")
        if not reason:
            return Response({"detail": "reason is required"}, status=400)
        app = PassApplication.objects.create(user=request.user, organisation=org, reason=reason)
        return Response(PassApplicationSerializer(app).data, status=201)


class PassMineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        my_pass = TransportPass.objects.filter(user=request.user, is_active=True).order_by("-created_at").first()
        latest_app = PassApplication.objects.filter(user=request.user).order_by("-created_at").first()
        return Response({
            "pass": TransportPassSerializer(my_pass).data if my_pass else None,
            "application": PassApplicationSerializer(latest_app).data if latest_app else None,
        })


class PassApplicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        qs = PassApplication.objects.all()
        org_ids = user_org_ids(request.user)
        if org_ids is not None:
            qs = qs.filter(organisation__in=org_ids)
        return Response(PassApplicationSerializer(qs.order_by("-created_at"), many=True).data)


class PassApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        app = PassApplication.objects.filter(pk=pk).first()
        if app is None:
            return Response({"detail": "Application not found"}, status=404)
        if not is_org_admin(request.user, app.organisation_id):
            return Response({"detail": "org_admin only"}, status=403)
        if app.status != "pending":
            return Response({"detail": f"Application already {app.status}"}, status=400)
        app.status = "approved"; app.reviewed_at = timezone.now(); app.save()
        now = timezone.now()
        transport_pass = TransportPass.objects.create(
            user=app.user, organisation=app.organisation, application=app,
            valid_from=now, valid_until=now + timedelta(days=180))
        log_audit(actor=request.user, organisation=app.organisation,
                  action="pass_approved", object_type="TransportPass", object_id=transport_pass.id,
                  detail=f"Pass application {app.id} approved for {app.user.email}")
        try:
            from notifications.services import notify
            notify(app.user, "pass", "Your transport pass is approved",
                   f"Your pass for {app.organisation.name} is valid until "
                   f"{transport_pass.valid_until.date().isoformat()}. Show the QR code when boarding.")
        except Exception:
            pass
        return Response(TransportPassSerializer(transport_pass).data, status=201)


class PassRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        app = PassApplication.objects.filter(pk=pk).first()
        if app is None:
            return Response({"detail": "Application not found"}, status=404)
        if not is_org_admin(request.user, app.organisation_id):
            return Response({"detail": "org_admin only"}, status=403)
        app.status = "rejected"; app.reviewed_at = timezone.now(); app.save()
        log_audit(actor=request.user, organisation=app.organisation,
                  action="pass_rejected", object_type="PassApplication", object_id=app.id,
                  detail=f"Pass application {app.id} rejected for {app.user.email}")
        try:
            from notifications.services import notify
            notify(app.user, "pass", "Your pass application was rejected",
                   f"Your pass application for {app.organisation.name} was not approved. "
                   "Contact your transport office for details.")
        except Exception:
            pass
        return Response(PassApplicationSerializer(app).data)


class PassVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = request.query_params.get("token", "")
        transport_pass = TransportPass.objects.filter(qr_token=token).first()
        if transport_pass is None:
            return Response({"valid": False, "detail": "Pass not found"}, status=404)
        now = timezone.now()
        valid = transport_pass.is_active and transport_pass.valid_from <= now <= transport_pass.valid_until
        return Response({"valid": valid, "pass": TransportPassSerializer(transport_pass).data})


class PassQRView(APIView):
    """GET /passes/{id}/qr/ — PNG QR of the pass qr_token (owner or org_admin)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        transport_pass = TransportPass.objects.filter(pk=pk).first()
        if transport_pass is None:
            return Response({"detail": "Pass not found"}, status=404)
        is_owner = transport_pass.user_id == request.user.id
        if not is_owner and not is_org_admin(request.user, transport_pass.organisation_id):
            return Response({"detail": "Pass not found"}, status=404)
        import qrcode

        img = qrcode.make(transport_pass.qr_token)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        response = HttpResponse(buf.getvalue(), content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="pass-{transport_pass.id}-qr.png"'
        return response


class JourneyPlanView(APIView):
    """GET /journey/plan/ — bidirectional planner (Wave 2).

    Lives in commuter (not tracking) because the tracking planner is
    forward-only and owned by the ML workstream. Same contract shape
    as before: {options: [...]} sorted fastest first.
    """

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
        options = plan_journey_bidirectional(from_id, to_id, user_org_ids(request.user))
        return Response({"options": options})


class ComplaintView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if is_org_admin(request.user):
            qs = Complaint.objects.all()
            org_ids = user_org_ids(request.user)
            if org_ids is not None:
                qs = qs.filter(organisation__in=org_ids)
        else:
            qs = Complaint.objects.filter(user=request.user)
        return Response(ComplaintSerializer(qs.order_by("-created_at"), many=True).data)

    def post(self, request):
        category = request.data.get("category", "other")
        if category not in dict(Complaint.CATEGORY_CHOICES):
            return Response({"detail": f"category must be one of {list(dict(Complaint.CATEGORY_CHOICES))}"}, status=400)
        complaint = Complaint.objects.create(
            user=request.user, organisation=_org_of_user(request.user),
            category=category, description=request.data.get("description", ""))
        return Response(ComplaintSerializer(complaint).data, status=201)


class ComplaintDetailView(APIView):
    """PATCH /complaints/{id}/ {status} — org_admin updates status (Wave 2).

    Notifies the reporter when the status actually changes.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        complaint = Complaint.objects.filter(pk=pk).first()
        if complaint is None:
            return Response({"detail": "Complaint not found"}, status=404)
        org_id = complaint.organisation_id
        if org_id is not None and not is_org_admin(request.user, org_id):
            return Response({"detail": "org_admin only"}, status=403)
        if org_id is None and not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        new_status = request.data.get("status")
        if new_status not in dict(Complaint.STATUS_CHOICES):
            return Response(
                {"detail": f"status must be one of {list(dict(Complaint.STATUS_CHOICES))}"}, status=400
            )
        old_status = complaint.status
        complaint.status = new_status
        complaint.save(update_fields=["status"])
        if new_status != old_status:
            try:
                from notifications.services import notify

                notify(complaint.user, "complaint", "Complaint update",
                       f"Your complaint ({complaint.category}) is now {new_status.replace('_', ' ')}.")
            except Exception:
                pass
        return Response(ComplaintSerializer(complaint).data)


class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_admin(request.user):
            return Response({"detail": "org_admin only"}, status=403)
        qs = Feedback.objects.all()
        org_ids = user_org_ids(request.user)
        if org_ids is not None:
            qs = qs.filter(vehicle__organisation__in=org_ids)
        return Response(FeedbackSerializer(qs.order_by("-created_at"), many=True).data)

    def post(self, request):
        rating = request.data.get("rating")
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return Response({"detail": "rating (1-5) is required"}, status=400)
        if not (1 <= rating <= 5):
            return Response({"detail": "rating must be between 1 and 5"}, status=400)
        fb = Feedback.objects.create(user=request.user, vehicle_id=request.data.get("vehicle"),
                                     rating=rating, comment=request.data.get("comment", ""))
        return Response(FeedbackSerializer(fb).data, status=201)


class IncidentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if is_org_admin(request.user):
            qs = Incident.objects.all()
            org_ids = user_org_ids(request.user)
            if org_ids is not None:
                qs = qs.filter(organisation__in=org_ids)
        else:
            qs = Incident.objects.filter(reporter=request.user)
        return Response(IncidentSerializer(qs.order_by("-created_at"), many=True).data)

    def post(self, request):
        inc_type = request.data.get("type", "")
        if not inc_type:
            return Response({"detail": "type is required"}, status=400)
        incident = Incident.objects.create(
            reporter=request.user, organisation=_org_of_user(request.user),
            vehicle_id=request.data.get("vehicle"), type=inc_type,
            description=request.data.get("description", ""))
        try:
            if incident.organisation_id:
                from notifications.services import notify_org_admins

                notify_org_admins(
                    incident.organisation_id, "incident",
                    f"New incident reported: {incident.type}",
                    incident.description or f"Incident #{incident.id} reported by {request.user.email}.",
                )
        except Exception:
            pass
        return Response(IncidentSerializer(incident).data, status=201)
