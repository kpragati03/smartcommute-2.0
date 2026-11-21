# SmartCommute 2.0 — Phase 1: Audit of SmartCommute Lite + Implementation Roadmap

Prepared 21 Nov 2026. Source audited: `~/workspace/smartcommute-lite/` (Django 5.1.15, SQLite, ~520 lines of core code).
SmartCommute Lite remains untouched as the college assignment. SmartCommute 2.0 is a separate, new project that reuses Lite's concepts (routes/stops/buses, device simulator, baseline ETA) and rebuilds everything else properly.

---

## 1. What exists today (verified by reading the code)

| Area | Current state |
|---|---|
| Models | 3 only: `Route`, `Stop`, `Bus`. Bus stores **current state only** (distance covered, speed, passengers, last_updated). No history, trips, schedules, users, or organisations. |
| Position model | 1-D "km from route start". No latitude/longitude anywhere → no map is possible without a schema change. |
| ETA | `Bus.eta_minutes_for(stop)` = remaining distance ÷ current speed. Returns `None` if passed/stopped. Clean, testable, and covered by tests. |
| API | One endpoint: `POST /api/location/` (manual JSON parsing, simple error JSON + status codes). No GET APIs, no versioning, no pagination, no serializers. |
| Frontend | One server-rendered template, inline CSS, full-page meta-refresh every 10 s. No JavaScript, no map, no search, no accounts. |
| Simulator | `simulate_device.py` — stdlib-only, one process per bus, posts every 10 s, loops the route, random speed jitter and passenger drift. No auth, no failure simulation. |
| Admin | Django Admin only. |
| Tests | 6 tests: ETA maths (3), seats clamp (1), device API happy path + unknown bus (2). All meaningful. |
| Seed data | 2 routes (Campus→City Centre 12.5 km, Campus→Railway Station 9.0 km), 9 stops, 3 buses. Idempotent re-seed. |

## 2. Audit findings

### Code quality — good for its size
- Small, readable, commented; clean separation of models/views/urls/template/simulator.
- Business logic (ETA, seats) lives on the model and is unit-tested.
- Gaps: no type hints, no logging, no service layer (logic will need extracting as features grow).

### Database design — the main structural limit
- **No history**: every device update overwrites the bus row. No `LocationHistory`, no `OccupancyRecord`, no trips → analytics, ETA learning, and anomaly detection are impossible today.
- **No geo data**: stops have no coordinates; routes have no polyline. Live maps and journey planning need lat/lng.
- **No tenancy/users**: no Organisation, User, Driver, Device, Schedule, Trip entities at all.
- **Missing constraints**: no unique `(route, order)` on stops; no check that stop distance ≤ route length; passengers can exceed capacity in storage (only clamped at display).

### API design — demo-grade
- Single write endpoint; the commuter UI is server-rendered, so there is no read API for a React frontend to consume.
- No input range validation (negative distance/speed, distance beyond route end, passengers > capacity are all accepted).
- No authentication, authorisation, rate limiting, or API versioning.

### Security — must fix before anything public
- `POST /api/location/` is `csrf_exempt` with **no authentication** — anyone who can reach the server can move any bus. (Documented as demo-only in the code; still the #1 fix: per-device API keys.)
- Hardcoded `django-insecure-` SECRET_KEY, `DEBUG=True`, localhost-only `ALLOWED_HOSTS` — development settings, not production.
- No audit logging, no HTTPS/deployment story.

### Frontend — a live board, not an app
- Meta-refresh reloads the whole page every 10 s; no live updates, map, search, journey planning, favourites, or accounts.
- The stop dropdown mixes stops from all routes, and ETAs are computed even for buses on other routes (meaningless values shown for cross-route pairs).
- Staleness is invisible: if a device dies, its bus still looks "live" forever (`last_updated` is stored but never checked).

### Performance / scalability
- Fine at demo scale (2 queries + a Python loop). SQLite's single-writer model will bottleneck once many devices post every few seconds → PostgreSQL in production.
- Simulator is one synchronous process per bus — fine for 3 buses, not for fleet-scale demos (needs a multi-bus mode).

## 3. What to preserve from Lite
- The baseline ETA maths + its tests (becomes the "mathematical baseline" the ML model is compared against).
- The device contract: `POST` JSON telemetry (extended with lat/lng + device key).
- The Phagwara seed routes/stops (extended with real coordinates).
- Django Admin as a fallback ops tool (the custom dashboard sits on top).
- The "distance along route" fallback for buses without GPS coordinates.

## 4. Target architecture (2.0)

- **Backend**: Django + Django REST Framework (versioned `/api/v1/`), JWT auth, role-based permissions, organisation-scoped querysets for tenant isolation. Django Channels for live updates (polling first; WebSockets when the map needs them). Celery + Redis only when a real async need appears (notifications, ETA jobs) — not on day one.
- **Database**: PostgreSQL in production (SQLite for local dev via env switch). Core entities: Organisation, Membership/Role, User, Vehicle, Driver, Route, Stop (lat/lng), Schedule, Trip, Device, LocationHistory, OccupancyRecord, ETAPrediction, Notification, TransportPass, Complaint, Feedback, Incident, Subscription, Invoice, AuditLog.
- **Frontend**: React (Vite) + React Router + Axios + Tailwind, Leaflet/OpenStreetMap for maps, Recharts for analytics. One app, role-based areas: commuter, driver, org admin, super admin.
- **Design direction** (Pragati's reference screenshots, 21 Nov 2026 — similar style, original implementation): neo-brutalist look — cream/off-white background, thick black borders on cards and inputs, bright lime-green primary with yellow and blue accents, bold display typography, pill badges and chunky pill buttons, card-based dashboards, a live Leaflet map panel with vehicle markers and stat cards ("buses live", "corridors"), role entry points (Student / Driver / Admin consoles) from the landing hero, and an organisation-registration flow. Use proper OpenStreetMap tiles (the reference screenshot shows a tile-provider "API KEY REQUIRED" watermark — avoid that).
- **Simulator 2.0**: multi-bus, moves along route polylines (real lat/lng), per-device API keys, simulated GPS dropouts/delays/breakdowns, passenger counter events at stops.
- **Intelligence**: baseline ETA (kept) vs scikit-learn ETA model trained on simulator-generated history, evaluated with MAE/RMSE on held-out trips — reported honestly, never fabricated. Rule-based anomaly detection first (stale GPS, deviation, jumps), ML only where data justifies it.
- **Cloud**: Vercel (frontend) + Render (backend) + managed PostgreSQL — same affordable pattern as HireLens. Env-based secrets, HTTPS, migrations on deploy, logging.

## 5. Prioritised roadmap (each phase ends working + tested)

| Phase | Deliverable | Why first |
|---|---|---|
| 1 | This audit + roadmap | Approval gate before big changes |
| 2 | Backend foundation: new project, DRF, core models (Org, Vehicle, Driver, Route/Stop+geo, Trip, Device, LocationHistory), device API v1 with API-key auth + validation, baseline ETA service, seed 2.0 | Everything else stands on this |
| 3 | Auth + roles + multi-org isolation (+ tenant-isolation tests) | Security core; retrofitting tenancy later is painful |
| 4 | React app shell + design system (Tailwind), auth screens | Frontend foundation |
| 5 | Commuter app: live map, bus discovery/search, journey planner (source→destination, transfers), crowd levels, favourites | **First deployable milestone — live link** |
| 6 | Driver portal + admin dashboard (fleet/routes/trips, live ops) | Operations side |
| 7 | Simulator 2.0 + live updates (WebSockets) | Makes the demo feel real |
| 8 | Digital passes (QR) + complaints/feedback | Passenger experience depth |
| 9 | Notifications + incidents | Communication layer |
| 10 | Intelligence: ML ETA vs baseline (MAE/RMSE), crowd prediction, anomaly rules, analytics dashboards | The "AI-powered" claim, done honestly |
| 11 | SaaS: org onboarding, plans, vehicle limits, billing records | Business foundation |
| 12 | Security hardening + full test suite + optimisation | Production readiness |
| 13 | Cloud deployment + production verification (auth, DB, simulator, maps, notifications all tested live) | Go-live |
| 14 | Business docs + pilot readiness | Sellable product |

**Honest scope note:** the full specification is a multi-week build for a small team. The plan above keeps a working, deployed product from Phase 5 onward, so there is always a live link to show — features then deepen phase by phase. Nothing is claimed done until it is tested.

## 6. Decisions needed before Phase 2
1. SmartCommute Lite stays exactly as-is for the college assignment; 2.0 is built separately. (Recommended.)
2. Build mode: Butter builds phase by phase (like HireLens) — per "Bna de ye project" — with a short report after each phase.
3. Priority vs Prospecta/FDE self-build: both are large; order is Pragati's call.
