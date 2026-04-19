"""AI analysis endpoint.

Accepts one uploaded image, runs the dual motorcycle/car detection pipeline,
and persists any violations found. Returns a list of Violation objects
(possibly empty). The request itself is always 200/201 - "no violation"
is represented as an empty list rather than an error.
"""
from pathlib import Path

from django.core.files.storage import default_storage
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Camera, Vehicle, LicensePlate, Violation, Evidence
from core.serializers import ViolationSerializer
from ai.infer import analyze_image


DEFAULT_FINE = {
    "no_helmet": 500,
    "no_seatbelt": 750,
}


class AnalyzeView(APIView):
    def post(self, request):
        img = request.FILES.get("image")
        if not img:
            return Response(
                {"error": "image is required (multipart/form-data key: image)"},
                status=400,
            )

        camera_name = (
            request.data.get("camera")
            or request.data.get("camera_name")
            or "Browser Webcam"
        )
        location = request.data.get("location") or "Live Camera"

        temp_path = default_storage.save(f"tmp/{img.name}", img)
        full_path = Path(default_storage.path(temp_path))

        debug = {}
        try:
            results = analyze_image(full_path, debug=debug)
        finally:
            try:
                default_storage.delete(temp_path)
            except Exception:
                pass

        if not results:
            # Build an informative message from the debug counts so the user
            # can tell whether the AI saw the vehicle at all.
            msg = _describe_scene(debug)
            return Response(
                {"message": msg, "violations": [], "debug": debug},
                status=200,
            )

        camera, _ = Camera.objects.get_or_create(
            name=camera_name,
            defaults={"location": location, "status": "online"},
        )

        created = []
        for r in results:
            plate_number = (r.get("plate_number") or "UNKNOWN").strip().upper() or "UNKNOWN"
            vehicle_type = r.get("vehicle_type") or "motorcycle"
            violation_type = r.get("violation_type") or "no_helmet"
            confidence = float(r.get("confidence") or 0.0)
            fine = DEFAULT_FINE.get(violation_type, 500)

            vehicle, created_flag = Vehicle.objects.get_or_create(
                plate_number=plate_number,
                defaults={"owner_name": "UNKNOWN", "vehicle_type": vehicle_type},
            )
            # If the vehicle was previously stored as a motorcycle and we now see
            # it as a car (or vice versa), keep the more-recent classification.
            if not created_flag and vehicle.vehicle_type != vehicle_type:
                vehicle.vehicle_type = vehicle_type
                vehicle.save(update_fields=["vehicle_type"])

            LicensePlate.objects.create(
                vehicle=vehicle,
                plate_number=plate_number,
                confidence_score=confidence,
            )

            violation = Violation.objects.create(
                vehicle=vehicle,
                camera=camera,
                violation_type=violation_type,
                fine_amount=fine,
                location=location,
                status="stored",
            )

            evidence_path = r.get("evidence_url") or ""
            if evidence_path:
                Evidence.objects.create(violation=violation, image_path=evidence_path)

            created.append(violation)

        return Response(
            {
                "violations": ViolationSerializer(created, many=True).data,
                "debug": debug,
            },
            status=201,
        )


def _describe_scene(debug: dict) -> str:
    """Build a human-readable message summarising what was detected."""
    if not debug:
        return "No violation detected"
    parts = []
    m = debug.get("motorcycles", 0)
    c = debug.get("cars", 0) + debug.get("trucks", 0) + debug.get("buses", 0)
    p = debug.get("persons", 0)
    pl = debug.get("plates", 0)

    if m == 0 and c == 0 and p == 0:
        return (
            "No motorcycles, cars, or people detected. "
            "Try a clearer image or a different angle."
        )

    scene = []
    if m:
        scene.append(f"{m} motorcycle{'s' if m > 1 else ''}")
    if c:
        scene.append(f"{c} car/truck/bus")
    if p:
        scene.append(f"{p} person/people")
    parts.append("Detected " + ", ".join(scene) + ".")

    if pl:
        parts.append(f"Found {pl} license plate{'s' if pl > 1 else ''}.")

    hw = debug.get("helmet_worn", 0)
    hnw = debug.get("helmet_not_worn", 0)
    if m and hw and not hnw:
        parts.append(
            "Helmet(s) appear to be worn — no violation. "
            "Upload a no-helmet photo to see a violation trigger."
        )
    elif m and not hw and not hnw:
        parts.append(
            "The helmet model didn't make a clear call on the rider. "
            "Try a closer shot of the rider's head."
        )

    mode = debug.get("seatbelt_mode")
    if c:
        if mode == "disabled":
            parts.append(
                "Seatbelt check is disabled (no seatbelt.pt and pose model not available)."
            )
        elif mode == "pose_heuristic":
            parts.append(
                "Seatbelt check used the pose-based heuristic. "
                "For reliable results, train seatbelt.pt — see README."
            )

    for note in debug.get("notes", []):
        parts.append(f"ℹ️ {note}")

    return " ".join(parts)
