from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Camera, Vehicle, Violation


class StatsView(APIView):
    """GET /api/stats/ -> totals + breakdowns for the dashboard."""

    def get(self, request):
        total_vehicles = Vehicle.objects.count()
        total_violations = Violation.objects.count()
        total_cameras = Camera.objects.count()

        by_type = list(
            Violation.objects.values("violation_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_status = list(
            Violation.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        recent = (
            Violation.objects.select_related("vehicle").order_by("-created_at")[:5]
        )
        recent_data = [
            {
                "id": v.id,
                "plate": v.vehicle.plate_number,
                "type": v.violation_type,
                "status": v.status,
                "created_at": v.created_at.isoformat(),
            }
            for v in recent
        ]

        return Response(
            {
                "vehicles_total": total_vehicles,
                "violations_total": total_violations,
                "cameras_total": total_cameras,
                "by_type": by_type,
                "by_status": by_status,
                "recent": recent_data,
            }
        )
