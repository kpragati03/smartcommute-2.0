"""Intelligence services (Phase 10): ML ETA prediction, crowd prediction,
rule-based anomaly detection.

ETA: predicts remaining travel time by summing per-segment predictions from
the trained GradientBoosting model (see training.py). Returns None whenever
the model is unavailable or the request is out of scope, so callers fall
back to the baseline ETA in tracking.services.

Crowd: historical average occupancy by (route, hour) from OccupancyRecord.
Returns level=None + reason="insufficient data" when there are too few
samples — never fabricates a level.

Anomalies: explainable rules over recent LocationHistory (stale GPS, route
deviation, speed jump, impossible jump) creating deduped Incident rows.
"""
import math
from datetime import timedelta
from pathlib import Path

import joblib
from django.conf import settings
from django.db.models.functions import ExtractHour
from django.utils import timezone

from fleet.models import Stop, Vehicle
from tracking.models import LocationHistory, OccupancyRecord
from tracking.services import haversine_km

from . import training as training_mod

# Crowd thresholds (API contract): <40% low, 40-75% moderate, >75% high.
CROWD_LOW_MAX = 40.0
CROWD_MODERATE_MAX = 75.0
CROWD_MIN_SAMPLES = 5

# Anomaly rule thresholds.
STALE_GPS_SECONDS = 120
DEVIATION_METERS = 300.0
SPEED_JUMP_KMPH = 60.0
IMPOSSIBLE_JUMP_KM = 2.0
IMPOSSIBLE_JUMP_SECONDS = 10.0
DEDUPE_MINUTES = 30

_bundle_cache = {"path": None, "mtime": None, "bundle": None}


def get_model_path():
    configured = getattr(settings, "INTELLIGENCE_ETA_MODEL_PATH", None)
    return Path(configured) if configured else training_mod.DEFAULT_MODEL_PATH


def load_bundle():
    """Load the trained ETA bundle, cached by path+mtime. None if unavailable."""
    path = get_model_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if _bundle_cache["path"] == str(path) and _bundle_cache["mtime"] == mtime:
        return _bundle_cache["bundle"]
    try:
        bundle = joblib.load(path)
    except Exception:
        return None
    _bundle_cache.update({"path": str(path), "mtime": mtime, "bundle": bundle})
    return bundle


def predict_eta_minutes(vehicle, stop, now=None):
    """ML ETA (minutes) for vehicle -> stop, or None to fall back to baseline.

    Sums predicted segment durations from the vehicle's current
    distance_covered_km through each intermediate stop to the target stop.
    """
    bundle = load_bundle()
    if bundle is None:
        return None
    if vehicle.current_route_id is None or stop.route_id != vehicle.current_route_id:
        return None
    start_km = float(vehicle.distance_covered_km or 0)
    target_km = float(stop.distance_from_start_km)
    if target_km <= start_km:
        return None  # already passed

    boundaries = [start_km]
    intermediate = Stop.objects.filter(
        route_id=stop.route_id,
        distance_from_start_km__gt=start_km,
        distance_from_start_km__lt=target_km,
    ).order_by("distance_from_start_km")
    boundaries += [float(s.distance_from_start_km) for s in intermediate]
    boundaries.append(target_km)

    now = now or timezone.now()
    local = timezone.localtime(now)
    hour, dow = local.hour, local.weekday()  # Mon=0, matches training CSV
    route_name = stop.route.name
    passengers = int(vehicle.passengers_onboard or 0)

    total = 0.0
    for a, b in zip(boundaries, boundaries[1:]):
        seg_km = b - a
        if seg_km <= 0:
            continue
        total += training_mod.predict_segment_minutes(
            bundle, seg_km, hour, dow, passengers, route_name)
    if total <= 0:
        return None
    return round(total, 1)


def crowd_level_for_percent(pct):
    if pct < CROWD_LOW_MAX:
        return "low"
    if pct <= CROWD_MODERATE_MAX:
        return "moderate"
    return "high"


def predict_crowd(route, hour, min_samples=CROWD_MIN_SAMPLES):
    """Predicted crowd level for (route, hour) from OccupancyRecord history."""
    records = (OccupancyRecord.objects
               .filter(vehicle__current_route=route)
               .annotate(rec_hour=ExtractHour("recorded_at"))
               .filter(rec_hour=hour)
               .select_related("vehicle"))
    percents = []
    for rec in records:
        cap = rec.vehicle.capacity
        if cap:
            percents.append(rec.passengers_onboard / cap * 100.0)
    n = len(percents)
    if n < min_samples:
        return {"level": None, "predicted_level": None,
                "avg_occupancy_percent": None, "samples": n,
                "reason": "insufficient data"}
    avg_pct = round(sum(percents) / n, 1)
    level = crowd_level_for_percent(avg_pct)
    return {"level": level, "predicted_level": level,
            "avg_occupancy_percent": avg_pct, "samples": n}


# ---------------------------------------------------------------------------
# Anomaly detection (rule-based, explainable)
# ---------------------------------------------------------------------------

def _point_to_segment_meters(lat, lng, a_lat, a_lng, b_lat, b_lng):
    """Distance (m) from point to segment AB via local equirectangular projection."""
    kx = 111320.0 * math.cos(math.radians(lat))  # meters per degree lng
    ky = 110540.0  # meters per degree lat
    px, py = lng * kx, lat * ky
    ax, ay = a_lng * kx, a_lat * ky
    bx, by = b_lng * kx, b_lat * ky
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_to_polyline_meters(lat, lng, polyline):
    """Min distance (m) from point to route polyline [[lat, lng], ...]."""
    if not polyline or len(polyline) < 2:
        return None
    return min(
        _point_to_segment_meters(lat, lng, p1[0], p1[1], p2[0], p2[1])
        for p1, p2 in zip(polyline, polyline[1:])
    )


def _system_reporter(vehicle):
    """User to attribute system-generated incidents to (Incident.reporter is required)."""
    from core.models import User

    admin = (User.objects.filter(memberships__organisation=vehicle.organisation,
                                 memberships__role="org_admin").first())
    if admin:
        return admin
    return (User.objects.filter(is_platform_admin=True).first()
            or User.objects.filter(is_superuser=True).first())


def _create_incident(vehicle, incident_type, description, now, create=True):
    """Create an Incident unless the same vehicle+type fired within DEDUPE_MINUTES."""
    from commuter.models import Incident

    recent = Incident.objects.filter(
        vehicle=vehicle, type=incident_type,
        created_at__gte=now - timedelta(minutes=DEDUPE_MINUTES)).exists()
    if recent:
        return "deduped"
    if not create:
        return "would_create"
    reporter = _system_reporter(vehicle)
    if reporter is None:
        return "no_reporter"
    return Incident.objects.create(
        reporter=reporter, organisation=vehicle.organisation, vehicle=vehicle,
        type=incident_type, description=description)


def detect_anomalies(hours=2, now=None, create=True):
    """Scan recent LocationHistory for anomalies; create deduped Incidents.

    Returns summary dict: {checked_vehicles, stale_gps, route_deviation,
    speed_jump, impossible_jump, incidents_created, skipped_no_reporter}.
    Counts are vehicles flagged per rule (one incident max per vehicle+type
    per run, further deduped across runs within 30 min).
    """
    now = now or timezone.now()
    since = now - timedelta(hours=hours)
    summary = {"checked_vehicles": 0, "stale_gps": 0, "route_deviation": 0,
               "speed_jump": 0, "impossible_jump": 0,
               "incidents_created": 0, "deduped": 0, "skipped_no_reporter": 0}

    vehicles = Vehicle.objects.filter(status="active").select_related("current_route")
    for vehicle in vehicles:
        summary["checked_vehicles"] += 1
        history = list(LocationHistory.objects.filter(vehicle=vehicle)
                       .order_by("recorded_at"))
        if not history:
            continue
        latest = history[-1]

        # Rule 1: stale GPS — active vehicle, no update for >120 s.
        age_s = (now - latest.recorded_at).total_seconds()
        if age_s > STALE_GPS_SECONDS:
            summary["stale_gps"] += 1
            res = _create_incident(
                vehicle, "stale_gps",
                f"[auto] No GPS update for {int(age_s)}s "
                f"(last at {latest.recorded_at.isoformat()}); threshold {STALE_GPS_SECONDS}s.",
                now, create)
            _tally(summary, res, create)

        window = [h for h in history if h.recorded_at >= since]
        if not window:
            continue

        # Rule 2: route deviation — point >300 m from route polyline.
        polyline = vehicle.current_route.polyline if vehicle.current_route else None
        if polyline:
            for point in window:
                dist_m = distance_to_polyline_meters(point.latitude, point.longitude, polyline)
                if dist_m is not None and dist_m > DEVIATION_METERS:
                    summary["route_deviation"] += 1
                    res = _create_incident(
                        vehicle, "route_deviation",
                        f"[auto] GPS point ({point.latitude}, {point.longitude}) is "
                        f"{dist_m:.0f}m from route polyline (threshold {DEVIATION_METERS:.0f}m) "
                        f"at {point.recorded_at.isoformat()}.",
                        now, create)
                    _tally(summary, res, create)
                    break

        # Rules 3+4: consecutive-point checks.
        speed_flagged = jump_flagged = False
        for prev, cur in zip(window, window[1:]):
            dt_s = (cur.recorded_at - prev.recorded_at).total_seconds()
            if not speed_flagged and abs(cur.speed_kmph - prev.speed_kmph) > SPEED_JUMP_KMPH:
                speed_flagged = True
                summary["speed_jump"] += 1
                res = _create_incident(
                    vehicle, "speed_jump",
                    f"[auto] Speed changed {prev.speed_kmph:.0f} -> {cur.speed_kmph:.0f} km/h "
                    f"between consecutive points (threshold {SPEED_JUMP_KMPH:.0f} km/h) "
                    f"at {cur.recorded_at.isoformat()}.",
                    now, create)
                _tally(summary, res, create)
            if not jump_flagged and 0 <= dt_s < IMPOSSIBLE_JUMP_SECONDS:
                moved_km = haversine_km(prev.latitude, prev.longitude,
                                        cur.latitude, cur.longitude)
                if moved_km > IMPOSSIBLE_JUMP_KM:
                    jump_flagged = True
                    summary["impossible_jump"] += 1
                    res = _create_incident(
                        vehicle, "impossible_jump",
                        f"[auto] Moved {moved_km:.2f} km in {dt_s:.0f}s "
                        f"(threshold {IMPOSSIBLE_JUMP_KM:.0f} km in <{IMPOSSIBLE_JUMP_SECONDS:.0f}s) "
                        f"at {cur.recorded_at.isoformat()}.",
                        now, create)
                    _tally(summary, res, create)
            if speed_flagged and jump_flagged:
                break
    return summary


def _tally(summary, result, create):
    if result == "deduped":
        summary["deduped"] += 1
    elif result == "no_reporter":
        summary["skipped_no_reporter"] += 1
    elif create and result != "would_create":
        summary["incidents_created"] += 1
