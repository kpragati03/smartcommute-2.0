from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "message", "is_read", "created_at"]


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notes = Notification.objects.filter(user=request.user).order_by("-created_at")
        return Response(NotificationSerializer(notes, many=True).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        note = Notification.objects.filter(pk=pk, user=request.user).first()
        if note is None:
            return Response({"detail": "Not found"}, status=404)
        note.is_read = True
        note.save(update_fields=["is_read"])
        return Response(NotificationSerializer(note).data)


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"status": "ok"})
