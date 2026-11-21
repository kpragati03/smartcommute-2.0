import hashlib
import secrets
from django.conf import settings
from django.db import models
from core.models import Organisation


class Route(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="routes")
    name = models.CharField(max_length=150)
    start_point = models.CharField(max_length=150)
    end_point = models.CharField(max_length=150)
    total_distance_km = models.FloatField(default=0)
    polyline = models.JSONField(default=list, blank=True)  # [[lat, lng], ...]
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organisation"])]

    def __str__(self):
        return f"{self.name} ({self.start_point} -> {self.end_point})"


class Stop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=150)
    order = models.PositiveIntegerField()
    distance_from_start_km = models.FloatField(default=0)
    latitude = models.FloatField(default=0)
    longitude = models.FloatField(default=0)

    class Meta:
        ordering = ["route", "order"]
        unique_together = [("route", "order")]

    def __str__(self):
        return f"{self.name} ({self.route.name} #{self.order})"


class Vehicle(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive"), ("maintenance", "Maintenance")]
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="vehicles")
    registration_number = models.CharField(max_length=30)
    capacity = models.PositiveIntegerField(default=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    current_route = models.ForeignKey(Route, null=True, blank=True, on_delete=models.SET_NULL, related_name="live_vehicles")
    # Live state, updated by device telemetry
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    distance_covered_km = models.FloatField(default=0)
    speed_kmph = models.FloatField(default=0)
    passengers_onboard = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registration_number"]
        unique_together = [("organisation", "registration_number")]
        indexes = [models.Index(fields=["organisation"])]

    def __str__(self):
        return self.registration_number

    @property
    def seats_available(self):
        return max(self.capacity - self.passengers_onboard, 0)

    @property
    def occupancy_percent(self):
        if not self.capacity:
            return 0
        return round((self.passengers_onboard / self.capacity) * 100, 1)

    @property
    def crowd_level(self):
        pct = self.occupancy_percent
        if pct < 40:
            return "low"
        if pct <= 75:
            return "moderate"
        return "high"

    def eta_minutes_for(self, stop):
        """Baseline ETA (from SmartCommute Lite): remaining distance / current speed."""
        remaining_km = stop.distance_from_start_km - self.distance_covered_km
        if remaining_km <= 0:
            return None
        if self.speed_kmph <= 0:
            return None
        return round((remaining_km / self.speed_kmph) * 60, 1)


class Driver(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive"), ("on_leave", "On Leave")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="driver_profiles")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="drivers")
    license_number = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        indexes = [models.Index(fields=["organisation"])]

    def __str__(self):
        return f"{self.user.email} ({self.organisation.name})"


class Schedule(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="schedules")
    departure_time = models.TimeField()
    days_of_week = models.CharField(max_length=30, default="1,2,3,4,5,6,7")  # ISO weekday numbers

    def __str__(self):
        return f"{self.route.name} @ {self.departure_time} ({self.days_of_week})"


class Trip(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"), ("running", "Running"), ("completed", "Completed"),
        ("cancelled", "Cancelled"), ("delayed", "Delayed"),
    ]
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="trips")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="trips")
    driver = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.SET_NULL, related_name="trips")
    scheduled_start = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    delay_minutes = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_start"]

    def __str__(self):
        return f"Trip {self.id} {self.route.name} {self.status}"


def hash_device_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_device_key():
    return secrets.token_urlsafe(32)


class Device(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="devices")
    device_key_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Device for {self.vehicle.registration_number}"
