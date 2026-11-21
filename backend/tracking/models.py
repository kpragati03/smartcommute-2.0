from django.db import models
from fleet.models import Vehicle, Stop


class LocationHistory(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="location_history")
    latitude = models.FloatField()
    longitude = models.FloatField()
    distance_covered_km = models.FloatField(default=0)
    speed_kmph = models.FloatField(default=0)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["vehicle", "recorded_at"])]


class OccupancyRecord(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="occupancy_records")
    passengers_onboard = models.PositiveIntegerField(default=0)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["vehicle", "recorded_at"])]


class ETAPrediction(models.Model):
    METHOD_CHOICES = [("baseline", "Baseline"), ("ml", "ML")]
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="eta_predictions")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="eta_predictions")
    predicted_eta_minutes = models.FloatField()
    actual_eta_minutes = models.FloatField(null=True, blank=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="baseline")
    created_at = models.DateTimeField(auto_now_add=True)
    # Phase 10 (ML intelligence): when actual_eta_minutes was filled by evaluate_etas.
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["vehicle", "stop"])]
