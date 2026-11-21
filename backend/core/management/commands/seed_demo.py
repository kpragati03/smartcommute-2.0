import json
from datetime import time, timedelta
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Organisation, User, Membership
from fleet.models import Route, Stop, Vehicle, Driver, Schedule, Trip, Device, hash_device_key, generate_device_key
from saas.models import SubscriptionPlan, Subscription


class Command(BaseCommand):
    help = "Seed SmartCommute 2.0 demo data (idempotent)."

    def handle(self, *args, **options):
        # Plans
        plans = {}
        for name, maxv, price in [("Starter", 5, 999), ("Growth", 25, 2999), ("Enterprise", 1000, 9999)]:
            plan, _ = SubscriptionPlan.objects.update_or_create(
                name=name, defaults={"max_vehicles": maxv, "price_monthly": price,
                                     "features": ["live_tracking", "journey_planner"]})
            plans[name] = plan

        # Organisations
        org1, _ = Organisation.objects.get_or_create(
            name="LPU Campus Transit (Demo)",
            defaults={"type": "university", "city": "Phagwara", "email": "transport@lpu.demo", "phone": "+91-0000000000"})
        org2, _ = Organisation.objects.get_or_create(
            name="City Transit Co (Demo)",
            defaults={"type": "city", "city": "Phagwara", "email": "admin@citytransit.demo", "phone": "+91-0000000001"})
        Subscription.objects.update_or_create(organisation=org1, defaults={"plan": plans["Growth"], "status": "active"})
        Subscription.objects.update_or_create(organisation=org2, defaults={"plan": plans["Starter"], "status": "active"})

        # Users
        def make_user(email, password, full_name, **extra):
            user, created = User.objects.get_or_create(email=email, defaults={"full_name": full_name, **extra})
            if created:
                user.set_password(password)
                user.save()
            return user

        platform_admin = make_user("admin@smartcommute.demo", "Admin@12345", "Platform Admin (Demo)",
                                   is_platform_admin=True, is_staff=True, is_superuser=True)
        org1_admin = make_user("transport@lpu.demo", "Admin@12345", "LPU Transport Admin (Demo)")
        driver_user = make_user("driver1@lpu.demo", "Driver@12345", "Demo Driver One")
        student = make_user("student1@lpu.demo", "Student@12345", "Demo Student One")
        org2_admin = make_user("admin@citytransit.demo", "Admin@12345", "City Transit Admin (Demo)")

        Membership.objects.get_or_create(user=org1_admin, organisation=org1, defaults={"role": "org_admin"})
        Membership.objects.get_or_create(user=driver_user, organisation=org1, defaults={"role": "driver"})
        Membership.objects.get_or_create(user=student, organisation=org1, defaults={"role": "commuter"})
        Membership.objects.get_or_create(user=org2_admin, organisation=org2, defaults={"role": "org_admin"})

        # Routes + stops (Phagwara / LPU area, approx coords)
        route1, _ = Route.objects.get_or_create(
            organisation=org1, name="Route 1 (Demo)",
            defaults={"start_point": "LPU Campus", "end_point": "City Centre", "total_distance_km": 12.5})
        route2, _ = Route.objects.get_or_create(
            organisation=org1, name="Route 2 (Demo)",
            defaults={"start_point": "LPU Campus", "end_point": "Phagwara Railway Station", "total_distance_km": 9.0})

        stops1 = [
            ("LPU Main Gate", 1, 0.0, 31.2550, 75.7050),
            ("Law Gate", 2, 1.2, 31.2490, 75.7010),
            ("Chaheru", 3, 4.0, 31.2400, 75.7300),
            ("Phagwara Bus Stand", 4, 8.0, 31.2240, 75.7700),
            ("Model Town", 5, 10.5, 31.2100, 75.7850),
            ("City Centre", 6, 12.5, 31.2000, 75.7900),
        ]
        stops2 = [
            ("LPU Main Gate", 1, 0.0, 31.2550, 75.7050),
            ("Law Gate", 2, 1.2, 31.2490, 75.7010),
            ("Chaheru", 3, 3.5, 31.2400, 75.7300),
            ("Phagwara Junction", 4, 6.5, 31.2250, 75.7650),
            ("Phagwara Railway Station", 5, 9.0, 31.2230, 75.7680),
        ]
        for route, stops in [(route1, stops1), (route2, stops2)]:
            polyline = []
            for name, order, dist, lat, lng in stops:
                Stop.objects.update_or_create(route=route, order=order, defaults={
                    "name": name, "distance_from_start_km": dist, "latitude": lat, "longitude": lng})
                polyline.append([lat, lng])
            route.polyline = polyline
            route.save(update_fields=["polyline"])

        # Org2 route (isolation proof)
        org2_route, _ = Route.objects.get_or_create(
            organisation=org2, name="City Loop (Demo)",
            defaults={"start_point": "City Centre", "end_point": "Bus Stand", "total_distance_km": 5.0})
        Stop.objects.update_or_create(route=org2_route, order=1, defaults={
            "name": "City Centre", "distance_from_start_km": 0.0, "latitude": 31.2000, "longitude": 75.7900})
        Stop.objects.update_or_create(route=org2_route, order=2, defaults={
            "name": "Phagwara Bus Stand", "distance_from_start_km": 5.0, "latitude": 31.2240, "longitude": 75.7700})
        org2_route.polyline = [[31.2000, 75.7900], [31.2240, 75.7700]]
        org2_route.save(update_fields=["polyline"])

        # Vehicles + devices
        vehicles_spec = [
            ("PB-10-AX-101", 40, route1), ("PB-10-AX-102", 35, route1), ("PB-10-BX-201", 40, route2),
        ]
        sim_vehicles = []
        for reg, cap, route in vehicles_spec:
            vehicle, _ = Vehicle.objects.get_or_create(
                organisation=org1, registration_number=reg,
                defaults={"capacity": cap, "status": "active", "current_route": route,
                          "current_latitude": 31.2550, "current_longitude": 75.7050})
            vehicle.current_route = route
            vehicle.save(update_fields=["current_route"])
            # Reuse existing device if present; key only known on first creation.
            # For idempotent demo runs, rotate key so config.json always matches DB.
            raw_key = generate_device_key()
            device, created = Device.objects.get_or_create(
                vehicle=vehicle, defaults={"device_key_hash": hash_device_key(raw_key)})
            if not created:
                device.device_key_hash = hash_device_key(raw_key)
                device.save(update_fields=["device_key_hash"])
            sim_vehicles.append({
                "registration_number": reg, "vehicle_id": vehicle.id,
                "device_key": raw_key, "route_id": route.id, "route_name": route.name,
                "capacity": cap,
                "route_polyline": route.polyline,
                "stops": [
                    {"name": s.name, "latitude": s.latitude, "longitude": s.longitude,
                     "distance_from_start_km": s.distance_from_start_km}
                    for s in route.stops.order_by("order")
                ],
            })
            self.stdout.write(f"Device key for {reg}: {raw_key}")

        # Driver profile
        driver, _ = Driver.objects.get_or_create(
            user=driver_user, organisation=org1,
            defaults={"license_number": "PB-DEMO-001", "phone": "+91-0000000002", "status": "active"})

        # Schedules
        for route in (route1, route2):
            for dep in [time(8, 0), time(9, 0), time(17, 0)]:
                Schedule.objects.get_or_create(route=route, departure_time=dep,
                                               defaults={"days_of_week": "1,2,3,4,5,6"})

        # Trips
        now = timezone.now()
        v1 = Vehicle.objects.get(organisation=org1, registration_number="PB-10-AX-101")
        v3 = Vehicle.objects.get(organisation=org1, registration_number="PB-10-BX-201")
        Trip.objects.get_or_create(route=route1, vehicle=v1, driver=driver,
                                   scheduled_start=now.replace(hour=8, minute=0, second=0, microsecond=0),
                                   defaults={"status": "running", "actual_start": now - timedelta(minutes=20)})
        Trip.objects.get_or_create(route=route2, vehicle=v3, driver=driver,
                                   scheduled_start=now.replace(hour=17, minute=0, second=0, microsecond=0),
                                   defaults={"status": "scheduled"})

        # Simulator config
        sim_dir = Path(__file__).resolve().parents[4] / "simulator"
        sim_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "api_base_url": "http://localhost:8000/api/v1",
            "telemetry_endpoint": "/devices/telemetry/",
            "vehicles": sim_vehicles,
        }
        (sim_dir / "config.json").write_text(json.dumps(config, indent=2))
        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Orgs={Organisation.objects.count()} Users={User.objects.count()} "
            f"Routes={Route.objects.count()} Vehicles={Vehicle.objects.count()} "
            f"Simulator config written to {sim_dir / 'config.json'}"))
