"""Bidirectional journey planner (Wave 2).

tracking/services.py only allows forward travel (a.order < b.order) and
belongs to the ML workstream, so Wave 2 implements reverse support here
in the commuter app and the /journey/plan/ route points at this service
(via commuter.views.JourneyPlanView). Routes are treated as traversable
in both directions: a leg is valid whenever the two stops differ, and
duration uses |distance difference| / avg speed (live avg per route,
fallback 25 km/h) + 5 min per transfer — matching the API contract.

Search depth mirrors the original: direct, 1-transfer, then 2-transfer
only when nothing simpler exists. Transfer points are stops with the
same name or within 0.5 km on another route.
"""
import math
from collections import defaultdict

from fleet.models import Stop, Vehicle

FALLBACK_SPEED_KMPH = 25.0
TRANSFER_PENALTY_MIN = 5.0


def _haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _avg_speed_for_route(route_id):
    speeds = list(
        Vehicle.objects.filter(current_route_id=route_id, speed_kmph__gt=0)
        .values_list("speed_kmph", flat=True)
    )
    if speeds:
        return sum(speeds) / len(speeds)
    return FALLBACK_SPEED_KMPH


def plan_journey_bidirectional(from_stop_id, to_stop_id, org_ids):
    """Return up to 5 journey options (fastest first), both directions."""
    stops_qs = Stop.objects.select_related("route").filter(route__is_active=True)
    if org_ids is not None:
        stops_qs = stops_qs.filter(route__organisation__in=org_ids)
    stops = list(stops_qs)
    by_id = {s.id: s for s in stops}
    if from_stop_id not in by_id or to_stop_id not in by_id:
        return []
    src, dst = by_id[from_stop_id], by_id[to_stop_id]
    if src.id == dst.id:
        return []

    routes = defaultdict(list)
    for s in stops:
        routes[s.route_id].append(s)
    for r in routes:
        routes[r].sort(key=lambda s: s.order)

    def transfer_targets(stop):
        out = []
        for s in stops:
            if s.route_id == stop.route_id:
                continue
            if s.name.strip().lower() == stop.name.strip().lower():
                out.append((s, 0.0))
            else:
                d = _haversine_km(stop.latitude, stop.longitude, s.latitude, s.longitude)
                if d <= 0.5:
                    out.append((s, d))
        return out

    def ride_legs(route_id, a, b):
        """Leg dict if a and b are distinct stops on the route (either direction)."""
        if a.route_id != route_id or b.route_id != route_id or a.id == b.id:
            return None
        dist = abs(b.distance_from_start_km - a.distance_from_start_km)
        speed = _avg_speed_for_route(route_id)
        dur = round((dist / speed) * 60, 1) if speed > 0 else 0
        return {
            "route_id": route_id,
            "route_name": a.route.name,
            "from_stop_id": a.id,
            "from_stop_name": a.name,
            "to_stop_id": b.id,
            "to_stop_name": b.name,
            "duration_minutes": dur,
        }

    options = []

    # Direct (forward or reverse)
    if src.route_id == dst.route_id:
        leg = ride_legs(src.route_id, src, dst)
        if leg:
            options.append({
                "legs": [leg],
                "total_duration_minutes": leg["duration_minutes"],
                "transfers": 0,
                "walking_km": 0.0,
            })

    # 1 transfer
    for x in routes[src.route_id]:
        leg1 = ride_legs(src.route_id, src, x)
        if not leg1:
            continue
        for (xp, walk) in transfer_targets(x):
            if xp.route_id != dst.route_id:
                continue
            leg2 = ride_legs(dst.route_id, xp, dst)
            if leg2:
                total = leg1["duration_minutes"] + leg2["duration_minutes"] + TRANSFER_PENALTY_MIN
                options.append({
                    "legs": [leg1, leg2],
                    "total_duration_minutes": round(total, 1),
                    "transfers": 1,
                    "walking_km": round(walk, 2),
                })

    # 2 transfers (only if nothing simpler)
    if not options:
        for x in routes[src.route_id]:
            leg1 = ride_legs(src.route_id, src, x)
            if not leg1:
                continue
            for (xp, walk1) in transfer_targets(x):
                for y in routes[xp.route_id]:
                    leg2 = ride_legs(xp.route_id, xp, y)
                    if not leg2:
                        continue
                    for (yp, walk2) in transfer_targets(y):
                        if yp.route_id != dst.route_id:
                            continue
                        leg3 = ride_legs(dst.route_id, yp, dst)
                        if leg3:
                            total = (
                                leg1["duration_minutes"]
                                + leg2["duration_minutes"]
                                + leg3["duration_minutes"]
                                + 2 * TRANSFER_PENALTY_MIN
                            )
                            options.append({
                                "legs": [leg1, leg2, leg3],
                                "total_duration_minutes": round(total, 1),
                                "transfers": 2,
                                "walking_km": round(walk1 + walk2, 2),
                            })

    seen, unique = set(), []
    for o in sorted(options, key=lambda o: o["total_duration_minutes"]):
        sig = tuple((l["route_id"], l["from_stop_id"], l["to_stop_id"]) for l in o["legs"])
        if sig not in seen:
            seen.add(sig)
            unique.append(o)
    return unique[:5]
