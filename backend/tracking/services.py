"""Baseline ETA service + journey planner (graph search, up to 2 transfers)."""
import math
from collections import defaultdict
from fleet.models import Stop, Vehicle

FALLBACK_SPEED_KMPH = 25.0
TRANSFER_PENALTY_MIN = 5.0


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def baseline_eta(vehicle, stop):
    """Returns (eta_minutes, distance_remaining_km) or None if passed / not moving."""
    remaining = stop.distance_from_start_km - vehicle.distance_covered_km
    if remaining <= 0:
        return None
    if vehicle.speed_kmph <= 0:
        return None
    return (round((remaining / vehicle.speed_kmph) * 60, 1), round(remaining, 2))


# --- ML INTELLIGENCE HOOK (Phase 10) ---------------------------------------
# ML-first ETA with baseline fallback. Baseline code above is untouched.
# Lazy import avoids a circular import (intelligence.services uses
# haversine_km from this module). Any ML failure silently falls back.
def eta_for_vehicle_stop(vehicle, stop):
    """Returns (eta_minutes, distance_remaining_km, method) or None.

    method is "ml" when the trained model produced the estimate, else
    "baseline" (existing behaviour, incl. the speed>0 requirement).
    """
    remaining = stop.distance_from_start_km - vehicle.distance_covered_km
    if remaining <= 0:
        return None
    try:
        from intelligence.services import predict_eta_minutes
        ml_eta = predict_eta_minutes(vehicle, stop)
    except Exception:
        ml_eta = None
    if ml_eta is not None:
        return (round(ml_eta, 1), round(remaining, 2), "ml")
    base = baseline_eta(vehicle, stop)
    if base is None:
        return None
    eta, rem = base
    return (eta, rem, "baseline")
# --- END ML INTELLIGENCE HOOK ----------------------------------------------


def _avg_speed_for_route(route_id):
    speeds = list(Vehicle.objects.filter(current_route_id=route_id, speed_kmph__gt=0).values_list("speed_kmph", flat=True))
    if speeds:
        return sum(speeds) / len(speeds)
    return FALLBACK_SPEED_KMPH


def plan_journey(from_stop_id, to_stop_id, org_ids):
    """Search direct + 1-transfer + 2-transfer options over the stop/route graph.

    Stops on the same route are rideable in order direction. A transfer happens
    at a stop shared by two routes (same stop row is per-route, so transfer
    points are stops with the same name, or nearby stops within 0.5 km).
    """
    stops_qs = Stop.objects.select_related("route").filter(route__is_active=True)
    if org_ids is not None:
        stops_qs = stops_qs.filter(route__organisation__in=org_ids)
    stops = list(stops_qs)
    by_id = {s.id: s for s in stops}
    if from_stop_id not in by_id or to_stop_id not in by_id:
        return []
    src, dst = by_id[from_stop_id], by_id[to_stop_id]

    routes = defaultdict(list)
    for s in stops:
        routes[s.route_id].append(s)
    for r in routes:
        routes[r].sort(key=lambda s: s.order)

    # transfer neighbours: stops with same name or within 0.5km on other routes
    def transfer_targets(stop):
        out = []
        for s in stops:
            if s.route_id == stop.route_id:
                continue
            if s.name.strip().lower() == stop.name.strip().lower():
                out.append((s, 0.0))
            elif haversine_km(stop.latitude, stop.longitude, s.latitude, s.longitude) <= 0.5:
                out.append((s, haversine_km(stop.latitude, stop.longitude, s.latitude, s.longitude)))
        return out

    def ride_legs(route_id, a, b):
        """Leg dict if a precedes b on route, else None."""
        if a.route_id != route_id or b.route_id != route_id or a.order >= b.order:
            return None
        dist = abs(b.distance_from_start_km - a.distance_from_start_km)
        speed = _avg_speed_for_route(route_id)
        dur = round((dist / speed) * 60, 1) if speed > 0 else 0
        return {"route_id": route_id, "route_name": a.route.name,
                "from_stop_id": a.id, "from_stop_name": a.name,
                "to_stop_id": b.id, "to_stop_name": b.name,
                "duration_minutes": dur}

    options = []

    # Direct
    if src.route_id == dst.route_id:
        leg = ride_legs(src.route_id, src, dst)
        if leg:
            options.append({"legs": [leg], "total_duration_minutes": leg["duration_minutes"],
                            "transfers": 0, "walking_km": 0.0})

    # 1 transfer: src --ride--> X (on src route), transfer to X' (other route), ride to dst
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
                options.append({"legs": [leg1, leg2], "total_duration_minutes": round(total, 1),
                                "transfers": 1, "walking_km": round(walk, 2)})

    # 2 transfers (only if nothing simpler, to keep results sane)
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
                            total = (leg1["duration_minutes"] + leg2["duration_minutes"]
                                     + leg3["duration_minutes"] + 2 * TRANSFER_PENALTY_MIN)
                            options.append({"legs": [leg1, leg2, leg3],
                                            "total_duration_minutes": round(total, 1),
                                            "transfers": 2, "walking_km": round(walk1 + walk2, 2)})

    # Dedupe by leg signature, sort fastest first, cap 5
    seen, unique = set(), []
    for o in sorted(options, key=lambda o: o["total_duration_minutes"]):
        sig = tuple((l["route_id"], l["from_stop_id"], l["to_stop_id"]) for l in o["legs"])
        if sig not in seen:
            seen.add(sig)
            unique.append(o)
    return unique[:5]
