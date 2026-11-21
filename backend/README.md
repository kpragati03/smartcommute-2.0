# SmartCommute 2.0 — Backend (Phases 2+3, Wave-2 hardening)

Django 5.1 + DRF + JWT backend for SmartCommute 2.0. Multi-tenant (organisation-scoped),
device telemetry with API-key auth, baseline ETA, journey planner, commuter/driver/SaaS APIs.

Wave 2 added: notification triggers, pass QR images, telemetry throttling,
reverse-direction journey planning, password reset, audit logging, and
production readiness (gunicorn + WhiteNoise + `render.yaml`).

## Setup (development)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

API base URL: `http://localhost:8000/api/v1/` · Django Admin: `http://localhost:8000/admin/`

## Production

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py migrate --noinput
.venv/bin/gunicorn smartcommute2.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Or deploy with the included `render.yaml` blueprint (web service + managed
Postgres). A `Procfile` is also included. In production set `DEBUG=false`
and a long random `SECRET_KEY` (Render's `generateValue` does this);
`python manage.py check --deploy` should then be clean. WhiteNoise serves
static files; `SECURE_*` headers (HSTS, secure cookies, SSL redirect)
activate automatically when `DEBUG=false`.

## Environment variables

| Var | Default | Notes |
|---|---|---|
| `SECRET_KEY` | `insecure-dev-only-change-me-in-production` | Long random value in production (never commit a real one) |
| `DEBUG` | `true` | `false` in production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated; on Render use `.onrender.com` or your domain |
| `DATABASE_URL` | (unset → SQLite `db.sqlite3`) | `postgres://user:pass@host:5432/dbname` for PostgreSQL (Render provides this) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated frontend origins |
| `FRONTEND_URL` | `http://localhost:5173` | Base URL for password-reset links in emails |
| `EMAIL_BACKEND` | console backend | SMTP backend in production (see `EMAIL_HOST*` below) |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` | — / `587` / — / — / `true` | SMTP settings when using the SMTP email backend |
| `DEFAULT_FROM_EMAIL` | `noreply@smartcommute.demo` | Sender for password-reset mail |
| `TELEMETRY_THROTTLE_RATE` | `120/min` | Per-device telemetry budget (keyed by device-key hash) |

See `.env.example`.

## Seed data

`seed_demo` is idempotent (safe to re-run; device keys rotate on each run so
`../simulator/config.json` always matches the database). It creates:

- 2 organisations: "LPU Campus Transit (Demo)" + "City Transit Co (Demo)" (isolation proof)
- Routes/stops with Phagwara/LPU coordinates + polylines, 3 vehicles + devices, schedules, trips
- Plans: Starter (5 vehicles, ₹999/mo), Growth (25, ₹2999), Enterprise (1000, ₹9999)
- Writes `../simulator/config.json` with `api_base_url` + per-vehicle device keys + polylines

### Demo credentials (local/dev only — seed-only, never use in production)

| Email | Password | Role |
|---|---|---|
| `admin@smartcommute.demo` | `Admin@12345` | Platform admin |
| `transport@lpu.demo` | `Admin@12345` | Org admin (Org 1) |
| `driver1@lpu.demo` | `Driver@12345` | Driver (Org 1) |
| `student1@lpu.demo` | `Student@12345` | Commuter (Org 1) |
| `admin@citytransit.demo` | `Admin@12345` | Org admin (Org 2) |

## Tests

```bash
.venv/bin/python manage.py test
```

Wave-1 baseline: 18 tests (auth, tenant isolation, telemetry validation,
baseline ETA, forward journey planner). Wave 2 adds 30 more: notification
triggers (delay/breakdown/trip-start/pass/incident/complaint), pass QR
PNG + permissions, telemetry throttling (429), reverse journeys,
password-reset flow, and audit-log writes. (The ML workstream adds its
own intelligence tests on top.)

## API overview

- Auth: `POST /auth/register|login|refresh/`, `GET /auth/me/`, `POST /auth/password-reset/` + `POST /auth/password-reset/confirm/`, `POST /organisations/register/`, `GET /organisations/` (platform admin)
- Fleet CRUD (org-scoped, org_admin writes): `/routes/ /stops/ /vehicles/ /drivers/ /schedules/ /trips/`
- Devices: `GET/POST /devices/` (raw key returned once), `POST /devices/telemetry/` (`X-Device-Key` header, throttled per device, 429 when exceeded)
- Live: `GET /live/vehicles/`, `GET /live/eta/?stop_id=`, `GET /journey/plan/?from_stop=&to_stop=` (both directions along a route)
- Commuter: `/favourites/routes/ /favourites/stops/ /journeys/saved/ /passes/* /complaints/ /feedback/ /incidents/ /notifications/*`
  - Pass QR image: `GET /passes/{id}/qr/` → `image/png` (pass owner or org_admin). Token check stays at `GET /passes/verify/?token=`.
  - Complaint status: `PATCH /complaints/{id}/` `{status}` (org_admin) — notifies the reporter.
- Driver: `GET /driver/my-trip/`, `POST /driver/trips/{id}/{start|end|delay|breakdown|passengers}/`, `GET /driver/history/`
- Analytics (org_admin): `/analytics/overview|routes|crowd|eta-accuracy/`
- SaaS: `GET /plans/`, `GET /subscription/`, `POST /subscription/upgrade/` (vehicle creation blocked at plan limit)

Full contract: `../API_CONTRACT.md`.

### Notifications (Wave 2)

Notifications are created automatically by `notifications/services.py`
(`notify(user, type, title, body)`):

| Event | Recipients |
|---|---|
| Driver reports delay | All commuter members of the org |
| Driver reports breakdown | Org commuters + org admins |
| Incident created | Org admins |
| Pass approved / rejected | The applicant |
| Complaint status changed | The reporter |
| Trip started | Commuters who favourited that route |

Read them via `GET /notifications/` (each has `type`, `title`, `message`).

### Analytics note: `total_passengers_today`

`GET /analytics/overview/` computes `total_passengers_today` as the sum
of today's `OccupancyRecord.passengers_onboard` snapshots. This is an
**approximation**: true boarding events don't exist yet, so the figure
over-counts anyone who stays on board across multiple telemetry pings
and depends on ping frequency. Treat it as a relative activity signal,
not an exact ridership count, until boarding/alighting events are added.

### Audit log (Wave 2)

`core.AuditLog` records org registration, vehicle create/delete, trip
start/end, pass approve/reject, subscription upgrade, and device
creation. View it read-only in Django Admin (`/admin/core/auditlog/`).

## Apps

- `core` — Organisation, custom User (email login), Membership, AuditLog, auth + password-reset views
- `fleet` — Route, Stop, Vehicle (live state), Driver, Schedule, Trip, Device, telemetry throttle
- `tracking` — LocationHistory, OccupancyRecord, ETAPrediction, ETA services, live views (ML workstream)
- `commuter` — favourites, saved journeys, passes (+ QR), complaints, feedback, incidents, bidirectional journey planner
- `notifications` — Notification + trigger service
- `saas` — SubscriptionPlan, Subscription, Invoice
- `intelligence` — analytics views + ML ETA (ML workstream)
