from rest_framework import serializers
from .models import Route, Stop, Vehicle, Driver, Schedule, Trip, Device


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ["id", "organisation", "name", "start_point", "end_point",
                  "total_distance_km", "polyline", "is_active"]


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = ["id", "route", "name", "order", "distance_from_start_km", "latitude", "longitude"]


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "organisation", "registration_number", "capacity", "status",
                  "current_route", "current_latitude", "current_longitude",
                  "distance_covered_km", "speed_kmph", "passengers_onboard", "last_updated"]


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "user", "organisation", "license_number", "phone", "status"]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ["id", "route", "departure_time", "days_of_week"]


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["id", "route", "vehicle", "driver", "scheduled_start",
                  "actual_start", "actual_end", "status", "delay_minutes", "notes"]


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "vehicle", "is_active", "last_seen", "created_at"]
