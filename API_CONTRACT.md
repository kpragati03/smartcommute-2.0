# SmartCommute 2.0 — API Contract (binding for all workstreams)

Base URL (dev): `http://localhost:8000/api/v1/`
All JSON. DRF pagination (page-number, page_size 20) on list endpoints.

## Auth
- User auth: JWT. Header `Authorization: Bearer <access>`.
  - `POST /auth/register/` `{email, password, full_name, phone?}` → 201 user
  - `POST /auth/login/` `{email, password}` → `{access, refresh}`
  - `POST /auth/refresh/` `{refresh}` → `{access}`
  - `GET /auth/me/` → `{id, email, full_name, phone, is_platform_admin, memberships:[{organisation_id, organisation_name, role}]}`
- Roles: `org_admin`, `driver`, `commuter`. Platform admin = `is_platform_admin` on user.
- Organisation registration (public): `POST /organisations/register/`
  `{name, type, city, email, phone, admin_name, admin_email, admin_password}` → 201 `{organisation, admin_user}` (creates org + org_admin membership).
- `GET /organisations/` platform-admin only.

## Tenant isolation rule (mandatory)
Every org-scoped endpoint filters by the caller's memberships. A user with no membership in an org gets 404/empty for that org's data — never another org's rows. Commuters see only their org's routes/vehicles. Tests must prove this.

## Core resources (org-scoped CRUD, org_admin writes; members read)
- `GET/POST /routes/`, `GET/PATCH/DELETE /routes/{id}/` — fields: id, organisation, name, start_point, end_point, total_distance_km, polyline [[lat,lng],...], is_active
- `GET/POST /stops/` (?route=), `GET/PATCH/DELETE /stops/{id}/` — id, route, name, order, distance_from_start_km, latitude, longitude (unique route+order)
- `GET/POST /vehicles/` — id, organisation, registration_number, capacity, status(active|inactive|maintenance)
- `GET/POST /drivers/` — id, user, organisation, license_number, phone, status
- `GET/POST /schedules/` — id, route, departure_time, days_of_week (e.g. "1,2,3,4,5")
- `GET/POST /trips/` — id, route, vehicle, driver, scheduled_start, actual_start, actual_end, status(scheduled|running|completed|cancelled|delayed)

## Device telemetry (device-key auth, NOT JWT)
- Header: `X-Device-Key: <key>` (keys stored hashed; key identifies the vehicle/device).
- `POST /devices/telemetry/` body `{latitude, longitude, distance_covered_km, speed_kmph, passengers_onboard, recorded_at?}` → 201 `{status:"ok"}`. Validation: lat -90..90, lng -180..180, speed 0..200, passengers 0..capacity, distance >= 0. Invalid key → 401. Writes LocationHistory + OccupancyRecord, updates vehicle live state + device last_seen.
- `GET /devices/` (org_admin) list devices; `POST /devices/` create (returns raw key ONCE).

## Live data (JWT, org-scoped)
- `GET /live/vehicles/` → `[{id, registration_number, route_id, route_name, latitude, longitude, distance_covered_km, speed_kmph, passengers_onboard, capacity, seats_available, occupancy_percent, crowd_level(low|moderate|high), last_updated, is_stale, status}]` (is_stale = last update > 60 s ago; crowd: <40% low, 40–75% moderate, >75% high)
- `GET /live/eta/?stop_id=` → `[{vehicle_id, registration_number, eta_minutes, method(baseline|ml), distance_remaining_km}]` (only vehicles on that stop's route, not yet passed)
- `GET /journey/plan/?from_stop=&to_stop=` → `{options:[{legs:[{route_id, route_name, from_stop_id, from_stop_name, to_stop_id, to_stop_name, duration_minutes}], total_duration_minutes, transfers, walking_km}]}` sorted fastest first. Duration = distance / avg speed (use live avg speed per route, fallback 25 km/h) + 5 min per transfer.

## Commuter features (JWT)
- `GET/POST/DELETE /favourites/routes/` `{route}` ; `GET/POST/DELETE /favourites/stops/` `{stop}`
- `GET/POST/DELETE /journeys/saved/` `{source_stop, destination_stop, label?}`
- Passes: `POST /passes/apply/` `{reason}` → PassApplication(pending); `GET /passes/mine/` → my pass + application status; `GET /passes/applications/` (org_admin); `POST /passes/applications/{id}/approve/` / `reject/` (org_admin) → creates TransportPass with qr_token; `GET /passes/verify/?token=` → pass validity (any authenticated user).
- Support: `POST/GET /complaints/` (category: missed_bus|wrong_eta|route_issue|lost_found|other; status open|in_progress|resolved); `POST /feedback/` `{vehicle?, rating 1-5, comment}`; `GET /feedback/` (org_admin).
- Incidents: `POST /incidents/` `{vehicle?, type, description}`; `GET /incidents/` (org_admin + reporter).
- Notifications: `GET /notifications/` (mine, newest first); `POST /notifications/{id}/read/`; `POST /notifications/read-all/`.

## Driver (JWT, role=driver)
- `GET /driver/my-trip/` → current/next assigned trip + stop sequence + progress
- `POST /driver/trips/{id}/start/`, `/end/`, `/delay/` `{minutes, note}`, `/breakdown/` `{note}`, `/passengers/` `{passengers_onboard}`
- `GET /driver/history/` past trips

## Analytics (org_admin)
- `GET /analytics/overview/` → {total_vehicles, active_vehicles, running_trips, delayed_trips, avg_occupancy_percent, total_passengers_today, open_complaints, devices_online, devices_offline}
- `GET /analytics/routes/` → per-route: trips, avg_delay_minutes, avg_occupancy, passengers
- `GET /analytics/crowd/` → occupancy by hour (from OccupancyRecord history)
- `GET /analytics/eta-accuracy/` → {baseline:{mae,rmse,n}, ml:{mae,rmse,n}} from stored evaluations (honest, computed from data)

## SaaS
- `GET /plans/` → [{id, name, max_vehicles, price_monthly, features}]
- `GET /subscription/` (org_admin) → current subscription; `POST /subscription/upgrade/` `{plan_id}` → switches plan, creates Invoice(status=pending; no real payment).
- Vehicle creation blocked (400) when org exceeds plan max_vehicles.

## Seed demo data (labelled DEMO)
- Org 1: "LPU Campus Transit (Demo)", type university, Phagwara. Org 2: "City Transit Co (Demo)" (isolation proof).
- Routes (Org 1): Route 1 Campus→City Centre 12.5 km; Route 2 Campus→Railway Station 9.0 km. Stops with coords (approx, Phagwara/LPU area): LPU Main Gate (31.2550,75.7050), Law Gate (31.2490,75.7010), Phagwara Bus Stand (31.2240,75.7700), Model Town (31.2100,75.7850), City Centre (31.2000,75.7900), Chaheru (31.2400,75.7300), Phagwara Junction (31.2250,75.7650), Phagwara Railway Station (31.2230,75.7680). Polylines through stop coords.
- Vehicles: PB-10-AX-101 (cap 40), PB-10-AX-102 (cap 35), PB-10-BX-201 (cap 40) + devices with keys (seed prints keys; also writes simulator/config.json).
- Demo users (local/dev only, documented in README): admin@smartcommute.demo/Admin@12345 (platform admin), transport@lpu.demo/Admin@12345 (org admin), driver1@lpu.demo/Driver@12345, student1@lpu.demo/Student@12345, admin@citytransit.demo/Admin@12345 (org 2 admin).
- Plans: Starter (5 vehicles, ₹999/mo), Growth (25, ₹2999), Enterprise (unlimited→1000, ₹9999). Prices configurable in DB.

## Frontend env
`VITE_API_URL` (default http://localhost:8000/api/v1). Tokens in localStorage; axios interceptor adds Bearer + refresh-on-401.

## Design tokens (neo-brutalist)
- bg cream `#FAF5E9`; ink `#141414`; lime `#B9E62E`; yellow `#FFD93D`; blue `#2F6BFF`; white cards.
- Borders: 2–3px solid ink; radius 14–20px; hard shadows `4px 4px 0 #141414`.
- Font: Archivo (headings, 800/900) + Inter (body) via @fontsource npm packages.
- Pill badges/buttons, chunky cards, Leaflet map with OSM tiles `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`.
