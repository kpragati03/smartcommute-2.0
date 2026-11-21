"""SmartCommute 2.0 GPS/device simulator (Phase 7 core).

Simulates on-bus GPS devices for multiple vehicles concurrently. Each vehicle
drives along its route polyline at a realistic speed, dwells at stops while
passengers board/alight, and POSTs telemetry to the backend exactly like a
real device would (see ../API_CONTRACT.md, "Device telemetry"):

    POST {api_base_url}/devices/telemetry/
    Header: X-Device-Key: <key>
    Body:   {latitude, longitude, distance_covered_km, speed_kmph,
             passengers_onboard, recorded_at}   (recorded_at = ISO8601 UTC)

Pure Python 3.12 standard library only (urllib for HTTP) — no pip deps.

Config: reads simulator/config.json when present (written by the backend
seed). If it is missing, falls back to a built-in demo config built from the
API contract's Phagwara routes/coords, with device keys taken from env vars
DEVICE_KEY_<REG> (dashes -> underscores) or --device-key CLI args.

Routes loop by REVERSING direction at the terminus (more realistic than
teleporting back to the start). distance_covered_km is always reported as
distance from the route start point along the polyline, in both directions.

Usage:
    python simulator.py [--config config.json] [--interval 5] [--speed 30]
                        [--duration 120] [--dropout-prob 0.05]
                        [--breakdown PB-10-AX-101] [--delay-factor 1.5]

Offline synthetic history export (no HTTP, for ML training data):
    python simulator.py --export-history history.csv --backfill-days 14 --seed 42

Press Ctrl+C to stop.
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

EARTH_RADIUS_KM = 6371.0
DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"
TELEMETRY_PATH = "/devices/telemetry/"


# --------------------------------------------------------------------------
# Geo helpers
# --------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lng points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class Polyline:
    """A route polyline with cumulative segment lengths for interpolation."""

    def __init__(self, points):
        if len(points) < 2:
            raise ValueError("polyline needs at least 2 points")
        self.points = [(float(lat), float(lng)) for lat, lng in points]
        self.cumulative_km = [0.0]
        for (lat1, lon1), (lat2, lon2) in zip(self.points, self.points[1:]):
            self.cumulative_km.append(
                self.cumulative_km[-1] + haversine_km(lat1, lon1, lat2, lon2))
        self.total_km = self.cumulative_km[-1]

    def interpolate(self, distance_km):
        """Return (lat, lng) at distance_km from the start (clamped to ends)."""
        if distance_km <= 0:
            return self.points[0]
        if distance_km >= self.total_km:
            return self.points[-1]
        # Find the segment containing distance_km.
        for i in range(1, len(self.cumulative_km)):
            if distance_km <= self.cumulative_km[i]:
                seg_start = self.cumulative_km[i - 1]
                seg_len = self.cumulative_km[i] - seg_start
                frac = 0.0 if seg_len == 0 else (distance_km - seg_start) / seg_len
                lat1, lon1 = self.points[i - 1]
                lat2, lon2 = self.points[i]
                return (lat1 + frac * (lat2 - lat1),
                        lon1 + frac * (lon2 - lon1))
        return self.points[-1]


def clamp_passengers(value, capacity):
    """Clamp a passenger count to [0, capacity]."""
    return max(0, min(capacity, int(value)))


# --------------------------------------------------------------------------
# Config loading (backend-seed config.json, else built-in demo fallback)
# --------------------------------------------------------------------------

# Stop coords from API_CONTRACT.md seed data (approx, Phagwara/LPU area).
DEMO_STOPS = {
    "LPU Main Gate": (31.2550, 75.7050),
    "Law Gate": (31.2490, 75.7010),
    "Chaheru": (31.2400, 75.7300),
    "Phagwara Bus Stand": (31.2240, 75.7700),
    "Model Town": (31.2100, 75.7850),
    "City Centre": (31.2000, 75.7900),
    "Phagwara Junction": (31.2250, 75.7650),
    "Phagwara Railway Station": (31.2230, 75.7680),
}

DEMO_ROUTES = {
    "Route 1 Campus to City Centre": [
        "LPU Main Gate", "Law Gate", "Chaheru",
        "Phagwara Bus Stand", "Model Town", "City Centre",
    ],
    "Route 2 Campus to Railway Station": [
        "LPU Main Gate", "Law Gate", "Chaheru",
        "Phagwara Junction", "Phagwara Railway Station",
    ],
}

DEMO_VEHICLES = [
    ("PB-10-AX-101", 40, "Route 1 Campus to City Centre"),
    ("PB-10-AX-102", 35, "Route 1 Campus to City Centre"),
    ("PB-10-BX-201", 40, "Route 2 Campus to Railway Station"),
]


def _stops_with_distances(stop_names):
    """Build stop dicts with cumulative distance_from_start_km (haversine)."""
    stops, dist, prev = [], 0.0, None
    for name in stop_names:
        lat, lng = DEMO_STOPS[name]
        if prev is not None:
            dist += haversine_km(prev[0], prev[1], lat, lng)
        stops.append({"name": name, "latitude": lat, "longitude": lng,
                      "distance_from_start_km": round(dist, 3)})
        prev = (lat, lng)
    return stops


def env_key_for(registration_number):
    """Env var name holding a vehicle's device key, e.g. DEVICE_KEY_PB_10_AX_101."""
    return "DEVICE_KEY_" + registration_number.replace("-", "_").upper()


def demo_config(device_key_overrides=None):
    """Built-in fallback config from the API contract's seed data."""
    device_key_overrides = device_key_overrides or {}
    vehicles = []
    for reg, capacity, route_name in DEMO_VEHICLES:
        stop_names = DEMO_ROUTES[route_name]
        key = (device_key_overrides.get(reg)
               or os.environ.get(env_key_for(reg))
               or f"demo-key-{reg.lower()}")
        vehicles.append({
            "registration_number": reg,
            "device_key": key,
            "route_name": route_name,
            "route_polyline": [list(DEMO_STOPS[n]) for n in stop_names],
            "stops": _stops_with_distances(stop_names),
            "capacity": capacity,
        })
    return {"api_base_url": DEFAULT_API_BASE_URL, "vehicles": vehicles}


def load_config(config_path, device_key_overrides=None):
    """Load config.json if present; otherwise return the demo fallback."""
    device_key_overrides = device_key_overrides or {}
    if config_path and os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as fh:
            config = json.load(fh)
        config.setdefault("api_base_url", DEFAULT_API_BASE_URL)
        for vehicle in config.get("vehicles", []):
            reg = vehicle.get("registration_number", "")
            if reg in device_key_overrides:
                vehicle["device_key"] = device_key_overrides[reg]
            elif not vehicle.get("device_key"):
                vehicle["device_key"] = os.environ.get(
                    env_key_for(reg), f"demo-key-{reg.lower()}")
        return config, True
    return demo_config(device_key_overrides), False


# --------------------------------------------------------------------------
# Telemetry posting
# --------------------------------------------------------------------------

def post_telemetry(api_base_url, device_key, payload, timeout=5):
    """POST one telemetry payload. Returns HTTP status code."""
    url = api_base_url.rstrip("/") + TELEMETRY_PATH
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Device-Key": device_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Per-vehicle simulation
# --------------------------------------------------------------------------

class VehicleSimulator(threading.Thread):
    """Simulates one bus driving back and forth along its route polyline."""

    def __init__(self, vehicle, api_base_url, args, stop_event):
        super().__init__(daemon=True, name=vehicle["registration_number"])
        self.reg = vehicle["registration_number"]
        self.device_key = vehicle["device_key"]
        self.capacity = int(vehicle.get("capacity", 40))
        # Accept both "route_polyline" (contract) and "polyline" (legacy seed output).
        self.polyline = Polyline(vehicle.get("route_polyline") or vehicle["polyline"])
        self.stops = sorted(vehicle.get("stops", []),
                            key=lambda s: s["distance_from_start_km"])
        self.api_base_url = api_base_url
        self.args = args
        self.stop_event = stop_event
        # Deterministic per-vehicle RNG (seed + reg) for reproducible runs.
        self.rng = random.Random(f"{args.seed}:{self.reg}")

        self.direction = 1  # +1 forward (start->end), -1 reverse
        self.distance_km = 0.0  # distance from route START along polyline
        self.passengers = clamp_passengers(self.rng.randint(5, 15), self.capacity)
        self.dwell_remaining_s = 0.0
        self.broken_down = False
        self.elapsed_s = 0.0
        self._warned_401 = False

    # -- movement ----------------------------------------------------------

    def _next_stop_distance(self):
        """Distance-from-start of the next stop ahead, or None at terminus."""
        ahead = [s["distance_from_start_km"] for s in self.stops
                 if (s["distance_from_start_km"] - self.distance_km) * self.direction > 0.01]
        if not ahead:
            return None
        return min(ahead) if self.direction > 0 else max(ahead)

    def _stop_event(self):
        """Boardings/alightings at a stop; returns dwell seconds."""
        alighting = self.rng.randint(0, max(0, self.passengers // 2))
        boarding = self.rng.randint(0, 8)
        self.passengers = clamp_passengers(
            self.passengers - alighting + boarding, self.capacity)
        return self.rng.uniform(20, 40)  # dwell 20-40 s

    def _advance(self, dt_s):
        """Advance the vehicle by dt_s seconds. Returns current speed km/h."""
        if self.broken_down:
            return 0.0
        if self.args.breakdown == self.reg and self.elapsed_s >= 30:
            # Breakdown: vehicle stops mid-route, keeps posting at speed 0.
            self.broken_down = True
            print(f"[{self.reg}] BREAKDOWN simulated at {self.distance_km:.2f} km "
                  f"— vehicle stopped, still posting telemetry.")
            return 0.0
        if self.dwell_remaining_s > 0:
            self.dwell_remaining_s = max(0.0, self.dwell_remaining_s - dt_s)
            return 0.0

        speed = self.args.speed + self.rng.uniform(-5, 5)  # jitter
        speed = max(5.0, speed) / max(0.1, self.args.delay_factor)
        step_km = speed * dt_s / 3600.0
        new_distance = self.distance_km + self.direction * step_km

        # Stop arrival: snap to the stop and dwell.
        next_stop = self._next_stop_distance()
        if next_stop is not None and (
                (self.direction > 0 and new_distance >= next_stop)
                or (self.direction < 0 and new_distance <= next_stop)):
            self.distance_km = next_stop
            self.dwell_remaining_s = self._stop_event()
            return 0.0

        # Terminus: reverse direction and dwell.
        if new_distance >= self.polyline.total_km or new_distance <= 0:
            self.distance_km = min(max(new_distance, 0.0), self.polyline.total_km)
            self.direction *= -1
            self.passengers = clamp_passengers(self.rng.randint(0, 5), self.capacity)
            self.dwell_remaining_s = self.rng.uniform(20, 40)
            print(f"[{self.reg}] terminus reached — reversing direction.")
            return 0.0

        self.distance_km = new_distance
        return speed

    # -- posting -----------------------------------------------------------

    def _post(self, speed):
        lat, lng = self.polyline.interpolate(self.distance_km)
        payload = {
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "distance_covered_km": round(self.distance_km, 3),
            "speed_kmph": round(speed, 1),
            "passengers_onboard": self.passengers,
            "recorded_at": iso_now(),
        }
        if self.rng.random() < self.args.dropout_prob:
            print(f"[{self.reg}] {self.distance_km:6.2f} km  {speed:4.0f} km/h  "
                  f"pax {self.passengers:2d}  DROPPED (simulated GPS dropout)")
            return
        try:
            status = post_telemetry(self.api_base_url, self.device_key, payload)
            print(f"[{self.reg}] {self.distance_km:6.2f} km  {speed:4.0f} km/h  "
                  f"pax {self.passengers:2d}  HTTP {status}")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                print(f"[{self.reg}] HTTP 401 — device key rejected — "
                      f"re-run backend seed to regenerate simulator/config.json")
            else:
                print(f"[{self.reg}] HTTP {exc.code} — telemetry rejected")
        except urllib.error.URLError:
            print(f"[{self.reg}] backend not reachable at {self.api_base_url} "
                  f"— retrying in {self.args.interval}s")

    def run(self):
        print(f"[{self.reg}] started — route {self.polyline.total_km:.2f} km, "
              f"capacity {self.capacity}, {len(self.stops)} stops")
        while not self.stop_event.is_set():
            speed = self._advance(self.args.interval)
            self._post(speed)
            self.elapsed_s += self.args.interval
            self.stop_event.wait(self.args.interval)
        print(f"[{self.reg}] stopped.")


# --------------------------------------------------------------------------
# Offline synthetic history export (for ML workstream; no HTTP)
# --------------------------------------------------------------------------

def export_history(config, out_path, days, seed):
    """Write N days of synthetic stop-to-stop trip rows to a CSV.

    Columns: timestamp, vehicle, route, stop_from, stop_to,
    duration_minutes, passengers, day_of_week (Mon=0), hour.
    Deterministic for a given seed. Labelled synthetic demo data.
    """
    rng = random.Random(seed)
    rows = []
    today = datetime.now(timezone.utc).date()
    for day_offset in range(days, 0, -1):
        day = today - timedelta(days=day_offset)
        for vehicle in config["vehicles"]:
            stops = sorted(vehicle.get("stops", []),
                           key=lambda s: s["distance_from_start_km"])
            if len(stops) < 2:
                continue
            route_name = vehicle.get("route_name", "Route")
            capacity = int(vehicle.get("capacity", 40))
            # Trips roughly hourly, 07:00-21:00, alternating direction.
            for trip_no, start_hour in enumerate(range(7, 22)):
                direction = 1 if trip_no % 2 == 0 else -1
                seq = stops if direction > 0 else list(reversed(stops))
                # Peak hours are slower.
                peak = start_hour in (8, 9, 17, 18, 19)
                avg_speed = rng.uniform(15, 22) if peak else rng.uniform(25, 38)
                passengers = clamp_passengers(rng.randint(3, 15), capacity)
                t = datetime(day.year, day.month, day.day, start_hour,
                             rng.randint(0, 20), tzinfo=timezone.utc)
                for a, b in zip(seq, seq[1:]):
                    seg_km = abs(b["distance_from_start_km"]
                                 - a["distance_from_start_km"])
                    duration = seg_km / avg_speed * 60 + rng.uniform(0.3, 0.7)
                    passengers = clamp_passengers(
                        passengers + rng.randint(-4, 6), capacity)
                    rows.append({
                        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "vehicle": vehicle["registration_number"],
                        "route": route_name,
                        "stop_from": a["name"],
                        "stop_to": b["name"],
                        "duration_minutes": round(duration, 2),
                        "passengers": passengers,
                        "day_of_week": day.weekday(),
                        "hour": t.hour,
                    })
                    t += timedelta(minutes=duration)
    rows.sort(key=lambda r: r["timestamp"])
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "timestamp", "vehicle", "route", "stop_from", "stop_to",
            "duration_minutes", "passengers", "day_of_week", "hour"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_device_key_args(pairs):
    overrides = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--device-key expects REG=KEY, got: {pair}")
        reg, key = pair.split("=", 1)
        overrides[reg.strip()] = key.strip()
    return overrides


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="SmartCommute 2.0 multi-bus GPS/device simulator.")
    parser.add_argument("--config", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config.json"),
        help="path to config.json (default: simulator/config.json; "
             "falls back to built-in demo config if missing)")
    parser.add_argument("--interval", type=float, default=5,
                        help="seconds between telemetry posts (default 5)")
    parser.add_argument("--speed", type=float, default=30,
                        help="cruising speed km/h before jitter (default 30)")
    parser.add_argument("--duration", type=float, default=0,
                        help="run for this many seconds then stop (0 = forever)")
    parser.add_argument("--dropout-prob", type=float, default=0.0,
                        help="probability of skipping a post (stale GPS), 0..1")
    parser.add_argument("--breakdown", metavar="REG", default=None,
                        help="registration number that breaks down mid-route")
    parser.add_argument("--delay-factor", type=float, default=1.0,
                        help=">1 slows all vehicles (e.g. 1.5 = 33%% slower)")
    parser.add_argument("--api-base-url", default=None,
                        help="override api_base_url from config")
    parser.add_argument("--device-key", action="append", metavar="REG=KEY",
                        help="override a vehicle's device key (repeatable)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducible runs (default 42)")
    parser.add_argument("--backfill-days", type=int, default=14,
                        help="days of synthetic history for --export-history")
    parser.add_argument("--export-history", metavar="PATH", default=None,
                        help="offline mode: write synthetic history CSV and exit")
    args = parser.parse_args(argv)

    overrides = parse_device_key_args(args.device_key)
    config, from_file = load_config(args.config, overrides)
    if args.api_base_url:
        config["api_base_url"] = args.api_base_url

    if args.export_history:
        n = export_history(config, args.export_history,
                           args.backfill_days, args.seed)
        print(f"Wrote {n} synthetic history rows to {args.export_history} "
              f"({args.backfill_days} days, seed {args.seed}). "
              f"Synthetic demo data — not real trips.")
        return 0

    source = args.config if from_file else "built-in demo fallback (no config.json)"
    print(f"SmartCommute 2.0 simulator — config: {source}")
    print(f"API base: {config['api_base_url']}  interval: {args.interval}s  "
          f"speed: {args.speed} km/h  dropout: {args.dropout_prob}  "
          f"delay-factor: {args.delay_factor}  breakdown: {args.breakdown or '-'}")
    if not from_file:
        print("NOTE: using demo device keys — the real backend will reply 401 "
              "until you run the backend seed (which writes config.json) or "
              "set DEVICE_KEY_<REG> env vars.")

    stop_event = threading.Event()
    threads = [VehicleSimulator(v, config["api_base_url"], args, stop_event)
               for v in config["vehicles"]]
    for t in threads:
        t.start()
    try:
        if args.duration > 0:
            stop_event.wait(args.duration)
        else:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        print("\nCtrl+C — stopping simulator...")
    stop_event.set()
    for t in threads:
        t.join(timeout=args.interval + 2)
    print("Simulator stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
