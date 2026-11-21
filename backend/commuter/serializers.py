from rest_framework import serializers
from .models import (FavouriteRoute, FavouriteStop, SavedJourney, PassApplication,
                     TransportPass, Complaint, Feedback, Incident)


class FavouriteRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavouriteRoute
        fields = ["id", "route", "created_at"]


class FavouriteStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavouriteStop
        fields = ["id", "stop", "created_at"]


class SavedJourneySerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedJourney
        fields = ["id", "source_stop", "destination_stop", "label", "created_at"]


class PassApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassApplication
        fields = ["id", "user", "organisation", "reason", "status", "created_at", "reviewed_at"]


class TransportPassSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportPass
        fields = ["id", "user", "organisation", "qr_token", "valid_from", "valid_until", "is_active", "created_at"]


class ComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = ["id", "user", "organisation", "category", "description", "status", "created_at"]


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "user", "vehicle", "rating", "comment", "created_at"]


class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = ["id", "reporter", "organisation", "vehicle", "type", "description", "created_at"]
