from rest_framework import serializers
from .models import Organisation, User, Membership


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "is_platform_admin"]


class MembershipSerializer(serializers.ModelSerializer):
    organisation_id = serializers.IntegerField(source="organisation.id", read_only=True)
    organisation_name = serializers.CharField(source="organisation.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["organisation_id", "organisation_name", "role"]


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name", "type", "city", "email", "phone", "created_at"]
