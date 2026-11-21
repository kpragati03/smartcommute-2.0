import secrets
from django.conf import settings
from django.db import models
from core.models import Organisation
from fleet.models import Route, Stop, Vehicle


def _make_qr_token():
    return secrets.token_urlsafe(24)


class FavouriteRoute(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favourite_routes")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="favourited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "route")]


class FavouriteStop(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favourite_stops")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="favourited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "stop")]


class SavedJourney(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_journeys")
    source_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="saved_from")
    destination_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="saved_to")
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PassApplication(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pass_applications")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="pass_applications")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)


class TransportPass(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transport_passes")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="transport_passes")
    application = models.OneToOneField(PassApplication, null=True, blank=True, on_delete=models.SET_NULL, related_name="issued_pass")
    qr_token = models.CharField(max_length=64, unique=True, default=_make_qr_token)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Complaint(models.Model):
    CATEGORY_CHOICES = [
        ("missed_bus", "Missed Bus"), ("wrong_eta", "Wrong ETA"), ("route_issue", "Route Issue"),
        ("lost_found", "Lost & Found"), ("other", "Other"),
    ]
    STATUS_CHOICES = [("open", "Open"), ("in_progress", "In Progress"), ("resolved", "Resolved")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints")
    organisation = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.CASCADE, related_name="complaints")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)


class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback")
    rating = models.PositiveSmallIntegerField()  # 1-5, validated at API level
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Incident(models.Model):
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incidents")
    organisation = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.CASCADE, related_name="incidents")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents")
    type = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
