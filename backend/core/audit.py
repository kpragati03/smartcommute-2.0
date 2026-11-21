"""Audit-log write helper (Wave 2).

Best-effort: audit failures must never break the primary request,
so ``log_audit`` swallows exceptions.
"""
from .models import AuditLog


def log_audit(actor=None, organisation=None, action="", object_type="", object_id="", detail=""):
    try:
        return AuditLog.objects.create(
            actor=actor if (actor is not None and getattr(actor, "pk", None)) else None,
            organisation=organisation,
            action=action,
            object_type=object_type or "",
            object_id=str(object_id) if object_id not in (None, "") else "",
            detail=detail or "",
        )
    except Exception:
        return None
