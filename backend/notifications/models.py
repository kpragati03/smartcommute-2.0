from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ("delay", "Delay"),
        ("breakdown", "Breakdown"),
        ("incident", "Incident"),
        ("pass", "Pass"),
        ("complaint", "Complaint"),
        ("trip", "Trip"),
        ("general", "General"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="general", db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
