# SmartCommute 2.0 — GPS/Device Simulator

Simulates on-bus GPS devices for **all configured vehicles concurrently**
(one thread per bus). Each bus drives along its route polyline at a realistic
speed, dwells at stops while passengers board/alight, reverses direction at
the terminus, and POSTs telemetry to the backend exactly like a real device:

```
POST {api_base_url}/devices/telemetry/
Header: X-Device-Key: <key>
Body:   {"latitude": ..., "longitude": ..., "distance_covered_km": ...,
         "speed_kmph": ..., "passengers_onboard": ...,
         "recorded_at": "2026-11-21T14:28:31Z"}   (ISO8601 UTC)
```

Pure Python 3.12 standard library only (`urllib` for HTTP) — no pip deps,
runs anywhere.

## Quick start

```bash
# 1. Start the backend and run its seed (writes simulator/config.json
#    with real device keys).
# 2. Run the simulator:
cd simulator
python simulator.py                      # forever, 5 s interval, Ctrl+C to stop
python simulator.py --duration 120       # stop after 120 s
```

## Config — two modes

### Mode 1: `config.json` (written by the backend seed) — preferred

If `simulator/config.json` exists it is used automatically (`--config PATH`
to point elsewhere). Format:

```json
{
  "api_base_url": "http://localhost:8000/api/v1",
  "vehicles": [
    {
      "registration_number": "PB-10-AX-101",
      "device_key": "<raw key from seed>",
      "route_name": "Route 1 Campus to City Centre",
      "route_polyline": [[31.2550, 75.7050], [31.2490, 75.7010], ...],
      "stops": [
        {"name": "LPU Main Gate", "latitude": 31.2550, "longitude": 75.7050,
         "distance_from_start_km": 0.0},
        ...
      ],
      "capacity": 40
    }
  ]
}
```

`route_name` is optional (used only in history export). Device keys in the
file can be overridden per vehicle with `--device-key REG=KEY`.

### Mode 2: built-in demo fallback (no config.json)

Uses the API contract's seed data: Route 1 Campus→City Centre and Route 2
Campus→Railway Station through the contract's Phagwara stop coords, vehicles
PB-10-AX-101 (cap 40), PB-10-AX-102 (cap 35), PB-10-BX-201 (cap 40).
Stop distances are computed by haversine along the stop coords (Route 1
≈ 11.2 km, Route 2 ≈ 7.8 km straight-line; contract totals 12.5/9.0 km are
road distances).

Device keys in fallback mode come from, in priority order:

1. `--device-key PB-10-AX-101=<key>` (repeatable)
2. Env var `DEVICE_KEY_PB_10_AX_101` (registration with dashes → underscores)
3. Placeholder `demo-key-pb-10-ax-101` — the real backend will reply **401**
   until the seed has run. The simulator prints a clear hint on 401:
   *"device key rejected — re-run backend seed"*.

## Behaviour

- **Movement:** position interpolated along the polyline by cumulative
  haversine segment lengths. Speed = `--speed` (default 30 km/h) ± 5 km/h
  jitter, divided by `--delay-factor`.
- **Stops:** on reaching a stop the bus dwells 20–40 s at speed 0;
  passengers change by random boardings/alightings, clamped to
  `0..capacity`.
- **Looping:** at the terminus the bus **reverses direction** (it does not
  teleport back to the start). `distance_covered_km` is always distance
  from the route start point, in both directions — so backend ETA logic
  (`distance_remaining`) works unchanged.
- **Logging:** one line per post per vehicle: distance km, speed,
  passengers, HTTP status. Clean Ctrl+C shutdown.

## Failure-simulation flags

| Flag | Effect |
|---|---|
| `--dropout-prob 0.05` | Skips ~5% of posts (stale GPS — backend `is_stale` after 60 s) |
| `--breakdown PB-10-AX-101` | That vehicle stops mid-route (after ~30 s), speed 0, keeps posting |
| `--delay-factor 1.5` | All vehicles run 33% slower (traffic) |

If the backend is unreachable the simulator prints
`backend not reachable at <url> — retrying in <interval>s` and keeps
retrying every interval — it never crashes on connection errors.

## Offline history export (ML training data)

The telemetry API only accepts live posts, so historical data is generated
offline instead:

```bash
python simulator.py --export-history history.csv --backfill-days 14 --seed 42
```

Writes synthetic stop-to-stop trip rows (no HTTP): trips roughly hourly
07:00–21:00 per vehicle, alternating direction, slower in peak hours
(08–09, 17–19). Deterministic for a given `--seed`.

Columns: `timestamp, vehicle, route, stop_from, stop_to, duration_minutes,
passengers, day_of_week` (Mon=0), `hour`.

**This is synthetic demo data**, labelled as such — for training/demoing the
ML ETA model, not real trips.

## CLI reference

```
python simulator.py [--config config.json] [--interval 5] [--speed 30]
                    [--duration 120] [--dropout-prob 0.05]
                    [--breakdown PB-10-AX-101] [--delay-factor 1.5]
                    [--api-base-url URL] [--device-key REG=KEY ...]
                    [--seed 42]
                    [--export-history history.csv] [--backfill-days 14]
```

`--duration 0` (default) runs until Ctrl+C.

## Tests

```bash
python -m unittest discover -s tests -v
```

Covers haversine sanity, polyline interpolation (midpoint/endpoints/clamps),
passenger clamping, config fallback + env/CLI key overrides, and history
export determinism/shape.

## How it pairs with the backend seed

1. Backend seed creates org/routes/stops/vehicles/devices and writes
   `simulator/config.json` with the raw device keys (keys are stored hashed
   server-side; the raw key is only available at creation).
2. Start the backend, then `python simulator.py` — buses appear on
   `GET /live/vehicles/` within one interval.
3. If you re-seed (new keys), just restart the simulator — it re-reads
   `config.json` at startup. A 401 in the logs means the keys are stale.
