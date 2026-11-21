def user_org_ids(user):
    """Organisation ids the user belongs to. Platform admin -> None (means all)."""
    if user.is_platform_admin or user.is_superuser:
        return None
    return list(user.memberships.values_list("organisation_id", flat=True))


def is_org_admin(user, org_id=None):
    if user.is_platform_admin or user.is_superuser:
        return True
    qs = user.memberships.filter(role="org_admin")
    if org_id is not None:
        qs = qs.filter(organisation_id=org_id)
    return qs.exists()


def user_role(user, org_id):
    m = user.memberships.filter(organisation_id=org_id).first()
    return m.role if m else None
