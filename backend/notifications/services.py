"""Notification trigger helpers (Wave 2).

Thin service layer over the Notification model so views stay small.
All helpers are best-effort: notification failures must never break the
primary action (delay report, pass approval, ...), so callers may wrap
in try/except; the helpers themselves do not raise for missing users.
"""
from core.models import Membership
from .models import Notification


def notify(user, type, title, body=""):
    """Create a single notification for *user*.

    Signature follows the Wave-2 spec: notify(user, type, title, body).
    ``type`` shadows the builtin intentionally to match the spec.
    Returns the created Notification or None if user is None.
    """
    if user is None:
        return None
    return Notification.objects.create(
        user=user, type=type or "general", title=title, message=body or ""
    )


def notify_users(users, type, title, body=""):
    """Bulk-create notifications for an iterable of users. Returns count."""
    users = [u for u in users if u is not None]
    if not users:
        return 0
    Notification.objects.bulk_create(
        [Notification(user=u, type=type or "general", title=title, message=body or "") for u in users]
    )
    return len(users)


def _org_users(organisation_id, role=None):
    qs = Membership.objects.filter(organisation_id=organisation_id).select_related("user")
    if role:
        qs = qs.filter(role=role)
    return [m.user for m in qs]


def notify_org_commuters(organisation_id, type, title, body=""):
    """Notify every commuter member of an organisation."""
    return notify_users(_org_users(organisation_id, role="commuter"), type, title, body)


def notify_org_admins(organisation_id, type, title, body=""):
    """Notify every org_admin member of an organisation."""
    return notify_users(_org_users(organisation_id, role="org_admin"), type, title, body)


def notify_route_favouriters(route_id, type, title, body=""):
    """Notify commuters who favourited a route (trip-started trigger)."""
    from commuter.models import FavouriteRoute

    user_ids = FavouriteRoute.objects.filter(route_id=route_id).values_list("user_id", flat=True)
    from django.contrib.auth import get_user_model

    users = list(get_user_model().objects.filter(id__in=list(user_ids)))
    return notify_users(users, type, title, body)
