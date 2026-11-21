from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class Organisation(models.Model):
    TYPE_CHOICES = [
        ("university", "University"), ("company", "Company"),
        ("school", "School"), ("city", "City Transit"), ("other", "Other"),
    ]
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="other")
    city = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_platform_admin", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_platform_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Membership(models.Model):
    ROLE_CHOICES = [
        ("org_admin", "Organisation Admin"),
        ("driver", "Driver"),
        ("commuter", "Commuter"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "organisation")]
        indexes = [models.Index(fields=["organisation"])]

    def __str__(self):
        return f"{self.user.email} @ {self.organisation.name} ({self.role})"


class AuditLog(models.Model):
    """Append-only audit trail (Wave 2). Read via Django Admin only."""

    ACTION_CHOICES = [
        ("org_registered", "Organisation registered"),
        ("vehicle_created", "Vehicle created"),
        ("vehicle_deleted", "Vehicle deleted"),
        ("trip_started", "Trip started"),
        ("trip_ended", "Trip ended"),
        ("pass_approved", "Pass approved"),
        ("pass_rejected", "Pass rejected"),
        ("subscription_upgraded", "Subscription upgraded"),
        ("device_created", "Device created"),
    ]
    actor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    organisation = models.ForeignKey(
        Organisation, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    object_type = models.CharField(max_length=50, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.object_type}#{self.object_id} @ {self.created_at}"
