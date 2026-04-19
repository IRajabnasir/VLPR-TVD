from django.utils import timezone
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Camera, Vehicle, Violation
from .serializers import CameraSerializer, VehicleSerializer, ViolationSerializer


class CameraViewSet(viewsets.ModelViewSet):
    queryset = Camera.objects.all().order_by("name")
    serializer_class = CameraSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all().order_by("plate_number")
    serializer_class = VehicleSerializer


class ViolationViewSet(viewsets.ModelViewSet):
    queryset = Violation.objects.all().select_related("vehicle", "camera").prefetch_related("evidence")
    serializer_class = ViolationSerializer

    def perform_update(self, serializer):
        """Auto-stamp reviewed_at/completed_at when status changes through them."""
        new_status = serializer.validated_data.get("status")
        instance = serializer.instance
        now = timezone.now()
        update_kwargs = {}
        if new_status and new_status != instance.status:
            if new_status == "reviewed" and instance.reviewed_at is None:
                update_kwargs["reviewed_at"] = now
            if new_status == "completed" and instance.completed_at is None:
                update_kwargs["completed_at"] = now
                if instance.reviewed_at is None:
                    update_kwargs["reviewed_at"] = now
        serializer.save(**update_kwargs)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        v = self.get_object()
        v.status = "reviewed"
        v.reviewed_at = timezone.now()
        v.save(update_fields=["status", "reviewed_at"])
        return Response(self.get_serializer(v).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        v = self.get_object()
        now = timezone.now()
        v.status = "completed"
        v.completed_at = now
        if v.reviewed_at is None:
            v.reviewed_at = now
        v.save(update_fields=["status", "reviewed_at", "completed_at"])
        return Response(self.get_serializer(v).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        v = self.get_object()
        v.status = "rejected"
        v.save(update_fields=["status"])
        return Response(self.get_serializer(v).data)
