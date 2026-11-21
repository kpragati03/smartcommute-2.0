# SmartCommute 2.0 — 5-Minute Demo Walkthrough

Prerequisite: backend + frontend running (locally or on the live URLs) and
the simulator running so buses move (`cd simulator && python simulator.py`).

## 1. Landing page (30 s)
Open the site. The hero shows the **live radar map** with buses moving along
their corridors, plus live counters (buses live, corridors). Note the
"demo data" labelling — everything is simulated.

## 2. Commuter flow (2 min)
Log in as **student1@lpu.demo / Student@12345**.
- Live map: bus markers move every few seconds; click a bus for speed,
  seats free and crowd level.
- Pick your stop → ETAs update live; stale buses are flagged.
- Journey planner: choose source and destination → direct and 1-transfer
  options with durations.
- Favourite a route; apply for a digital pass and show its QR code.
- Notifications bell: delay/arrival alerts appear here.

## 3. Driver flow (1 min)
Log in as **driver1@lpu.demo / Driver@12345**.
- See the assigned trip and stop sequence; start the trip.
- Update passenger count with the stepper; report a delay — commuters who
  favourited the route get a notification.

## 4. Admin flow (1.5 min)
Log in as **transport@lpu.demo / Admin@12345**.
- Overview: active buses, occupancy, route performance charts, ETA accuracy.
- Fleet & devices: vehicles, device keys (shown once at creation).
- Routes/stops, trips/schedules, drivers — full CRUD.
- Approve the pass applied for in step 2; check the complaints inbox.
- Subscription page: current plan and vehicle limit.

## 5. Platform admin (30 s)
Log in as **admin@smartcommute.demo / Admin@12345** → Organisations page:
both demo organisations, plans, and usage. Emphasise tenant isolation: the
LPU admin cannot see City Transit's data (covered by automated tests).

## Talking points
- Security: per-device API keys (hashed), JWT + roles, org isolation, rate
  limiting, audit log.
- Honest ML: baseline vs ML ETA compared on held-out data; synthetic-data
  caveat stated in the UI; retrains on real history after a pilot.
- Ready for real hardware: swap the simulator for real GPS devices posting
  the same telemetry contract.
