# SmartCommute 2.0 — Intelligent Transit & Fleet Management Ecosystem

A cloud-hosted, multi-organisation smart mobility platform: live bus tracking,
intelligent journey planning, ML-assisted ETA prediction, passenger occupancy
intelligence, fleet & driver management, digital transport passes, complaints
and incident handling, real-time notifications, operational analytics, and
SaaS subscription management — built for universities, schools, and corporate
transport departments.

> **Demo data notice:** all organisations, routes, vehicles, users and
> telemetry in the seed/demo environment are **simulated demo data**. GPS data
> comes from the included device simulator — no physical hardware is required,
> and the architecture is ready for real IoT devices later.

**Live demo:** https://smartcommute-2-0.vercel.app (frontend) ·
https://smartcommute-backend.onrender.com/api/v1 (API). Demo logins are in
the "Demo accounts" section below. The free backend sleeps when idle, so the
first load after a pause can take ~30–60 s.

## What it does

- **Commuter app** — live Leaflet map with moving buses, stop/route search,
  upcoming arrivals with ETA, crowd levels (low/moderate/high), a journey
  planner that finds direct and 1-transfer routes, favourites & saved
  journeys, digital transport pass with QR, complaints/feedback/incidents,
  and in-app notifications (delays, arrivals, pass status).
- **Driver portal** — assigned vehicle/route, start/end trip, stop sequence
  with progress, passenger count updates, delay & breakdown reporting.
- **Admin console** — fleet, routes/stops, schedules/trips, drivers, device
  keys, pass approvals, complaints inbox, incidents, analytics (crowd by
  hour, route performance, ETA accuracy), and subscription/plan management.
- **Multi-organisation SaaS** — every organisation's users, routes, vehicles,
  drivers and trips are fully isolated (enforced and tested); platform admin
  manages organisations and plans; per-plan active-vehicle limits.
- **Intelligence** — a mathematical baseline ETA (distance ÷ speed) plus a
  gradient-boosting ETA model trained on simulator history. On held-out
  **synthetic** test data (n=1,260): baseline MAE 1.454 min vs ML MAE
  0.624 min. This measures fit to the simulator's patterns, not real-world
  accuracy — the model is retrained on real `LocationHistory` after a pilot.
  Rule-based anomaly detection flags stale GPS, route deviation and
  impossible jumps as incidents.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite), React Router, Tailwind CSS, Leaflet + OpenStreetMap, Recharts, Axios |
| Backend | Python, Django 5.1, Django REST Framework, JWT auth |
| Database | PostgreSQL (production), SQLite (local dev) |
| ML | scikit-learn, pandas, NumPy |
| Simulator | Python 3 standard library only |
| Hosting | Vercel (frontend), Render (backend + managed PostgreSQL) |

## Repository layout

```
backend/     Django + DRF API (7 apps: core, fleet, tracking, commuter,
             notifications, saas, intelligence) — see backend/README.md
frontend/    React app (landing, commuter, driver, admin consoles)
simulator/   Multi-bus GPS/device simulator — see simulator/README.md
render.yaml  Render Blueprint (web service + Postgres)
API_CONTRACT.md   Full REST API contract
PHASE_REPORTS.md  Build log per phase
```

## Run locally

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver        # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env                         # VITE_API_URL=http://localhost:8000/api/v1
npm run dev                                  # http://localhost:5173

# Simulator (new terminal, after seed_demo wrote simulator/config.json)
cd simulator
python simulator.py                          # buses start moving on the map
```

### Demo logins (seed data only)

| Role | Email | Password |
|---|---|---|
| Platform admin | admin@smartcommute.demo | Admin@12345 |
| Org admin (LPU demo org) | transport@lpu.demo | Admin@12345 |
| Driver | driver1@lpu.demo | Driver@12345 |
| Commuter/student | student1@lpu.demo | Student@12345 |
| Org admin (City Transit demo org) | admin@citytransit.demo | Admin@12345 |

## Tests

```bash
cd backend && .venv/bin/python manage.py test     # API, auth, tenant isolation, ETA, ML
cd simulator && python -m pytest tests/ -q        # simulator behaviour
cd frontend && npm run build                      # production build check
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md). In short: Render Blueprint for the
backend + PostgreSQL, Vercel for the frontend, then seed + train the ETA
model on production (the trained model file is a generated artifact and is
never committed).

## Demo walkthrough

See [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) for a 5-minute guided tour.

## Security notes

- Device telemetry requires a per-device API key (stored SHA-256-hashed),
  with input validation and per-device rate limiting.
- JWT authentication + role-based permissions; every organisation-scoped
  endpoint filters by the caller's organisation.
- Secrets come from environment variables only; production settings enable
  HTTPS/HSTS/secure cookies automatically when `DEBUG=false`.
