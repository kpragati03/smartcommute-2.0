# SmartCommute 2.0 — Frontend

React (Vite) + Tailwind + Leaflet frontend for SmartCommute 2.0.

## Run
```bash
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000/api/v1
npm run dev            # http://localhost:5173
npm run build          # production build -> dist/
npm run preview
```

## Demo logins (local dev only)
- student1@lpu.demo / Student@12345 (commuter)
- driver1@lpu.demo / Driver@12345 (driver)
- transport@lpu.demo / Admin@12345 (org admin)
- admin@smartcommute.demo / Admin@12345 (platform admin)

## Routes
`/` landing + live radar · `/login` · `/register` · `/register-organisation` ·
`/app` commuter (protected) · `/driver` driver portal · `/admin` admin console

## Consoles (Wave 2)
- **Commuter (`/app`)** — live map/vehicles/ETA/journey planner/favourites (Wave 1)
  plus: transport pass (apply, status, QR from `GET /passes/{id}/qr/` with a
  client-side `qrcode` fallback that renders the `qr_token`), support (complaints
  incl. lost & found with status tracking, star feedback, incident reports), and a
  notifications bell in the navbar (polls every 30 s, unread count, mark read / read-all).
- **Driver (`/driver`)** — current/next trip with stop sequence + progress
  (km covered, stops passed, next stop), big Start/End buttons, report delay
  (minutes + note), report breakdown (note), passenger stepper
  (`POST /driver/trips/{id}/passengers/`), trip history.
- **Admin (`/admin`)** — tabbed console: Overview (stat cards + recharts
  crowd-by-hour, route performance, honest baseline-vs-ML ETA accuracy),
  Fleet & devices (vehicle create/edit; device create with the raw key shown
  ONCE in a copyable box; deactivate), Routes & stops (polyline as
  `lat,lng` per line; per-route stops CRUD), Trips & schedules, Drivers
  (link existing user by email), Pass applications (approve/reject),
  Complaints inbox (status + resolution note) + rider feedback, Incidents,
  Subscription (current plan, plans grid, upgrade; invoices shown only if the
  backend exposes an invoices endpoint), Organisations (platform admin only).

Live data polls every 5s. When the API is unreachable the UI shows a "connecting" state — it never invents buses.
