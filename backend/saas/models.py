from django.db import models
from core.models import Organisation


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    max_vehicles = models.PositiveIntegerField(default=5)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    features = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.name} (max {self.max_vehicles} vehicles)"


class Subscription(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")]
    organisation = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.organisation.name} -> {self.plan.name}"


class Invoice(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")]
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="invoices")
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
