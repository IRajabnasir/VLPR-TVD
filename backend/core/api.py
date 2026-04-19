from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Camera, Vehicle, LicensePlate, Violation, Evidence
from .serializers import DetectionCreateSerializer, ViolationSerializer


@api_view(["POST"])
def create_detection(request):
    """Create a violation manually (useful for tests / bulk-imports)."""
    serializer = DetectionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    plate_number = data["plate_number"].strip().upper()
    owner_name = (data.get("owner_name") or "").strip()

    vehicle, created = Vehicle.objects.get_or_create(
        plate_number=plate_number,
        defaults={"owner_name": owner_name},
    )
    if (not created) and owner_name and not vehicle.owner_name:
        vehicle.owner_name = owner_name
        vehicle.save(update_fields=["owner_name"])

    # Log the OCR read
    LicensePlate.objects.create(
        vehicle=vehicle,
        plate_number=plate_number,
        confidence_score=float(data.get("confidence_score") or 0.0),
    )

    camera = None
    cam_id = data.get("camera_id")
    if cam_id:
        camera = Camera.objects.filter(pk=cam_id).first()

    violation = Violation.objects.create(
        vehicle=vehicle,
        camera=camera,
        violation_type=data["violation_type"],
        fine_amount=data.get("fine_amount") or 0,
        location=data.get("location", ""),
        status="stored",
    )

    evidence_url = data.get("evidence_url", "").strip()
    if evidence_url:
        Evidence.objects.create(violation=violation, image_path=evidence_url)

    return Response(ViolationSerializer(violation).data, status=status.HTTP_201_CREATED)
