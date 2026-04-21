from rest_framework import serializers

from .models import Camera, Vehicle, LicensePlate, Violation, Evidence


class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = "__all__"


class LicensePlateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicensePlate
        fields = ["id", "plate_number", "confidence_score", "created_at"]


class VehicleSerializer(serializers.ModelSerializer):
    plate_reads = LicensePlateSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id", "plate_number", "vehicle_type", "color", "owner_name", "plate_reads",
        ]


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = ["id", "image_path", "capture_time"]


class ViolationSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)
    vehicle_type = serializers.CharField(source="vehicle.vehicle_type", read_only=True)
    evidence = EvidenceSerializer(many=True, read_only=True)
    evidence_url = serializers.CharField(read_only=True)  # convenience: first image
    camera_name = serializers.CharField(source="camera.name", read_only=True, default="")

    class Meta:
        model = Violation
        fields = [
            "id",
            "vehicle", "vehicle_plate", "vehicle_type",
            "camera", "camera_name",
            "violation_type",
            "fine_amount",
            "speed_kmh",
            "location",
            "status",
            "created_at",
            "reviewed_at",
            "completed_at",
            "evidence",
            "evidence_url",
        ]
        read_only_fields = ["created_at", "reviewed_at", "completed_at", "evidence_url"]


class DetectionCreateSerializer(serializers.Serializer):
    """Manual detection creation payload (used by /api/detections/)."""
    plate_number = serializers.CharField(max_length=32)
    owner_name = serializers.CharField(max_length=128, required=False, allow_blank=True)

    violation_type = serializers.CharField(max_length=32)
    fine_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    evidence_url = serializers.CharField(required=False, allow_blank=True)
    confidence_score = serializers.FloatField(required=False, default=0.0)
    camera_id = serializers.IntegerField(required=False)
