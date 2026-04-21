"""Domain models aligned with the D1 class diagram.

Entities:
  - Camera         : physical/virtual camera feeding the system
  - Vehicle        : a detected vehicle
  - LicensePlate   : plate reading (own entity because a vehicle can have
                     multiple OCR attempts with different confidence scores)
  - Violation      : a traffic violation event
  - Evidence       : image evidence attached to a violation

Violation.status follows the D1 state chart:
    Idle -> Detected -> Stored -> Reviewed -> Completed
    (plus a Rejected outlier for admin-discarded violations)
"""
from django.db import models


class Camera(models.Model):
    """A camera source (physical CCTV, IP cam, or browser webcam)."""
    STATUS_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
    ]

    name = models.CharField(max_length=64, unique=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="online")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    """A detected vehicle. plate_number here is the canonical/best-known plate."""
    plate_number = models.CharField(max_length=32, unique=True)
    vehicle_type = models.CharField(max_length=32, blank=True, default="motorcycle")
    color = models.CharField(max_length=32, blank=True)
    owner_name = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.plate_number


class LicensePlate(models.Model):
    """A single OCR read of a license plate. Multiple rows per vehicle allowed."""
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="plate_reads"
    )
    plate_number = models.CharField(max_length=32)
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.plate_number} ({self.confidence_score:.2f})"


class Violation(models.Model):
    """A traffic violation following the D1 state chart lifecycle."""
    STATUS_CHOICES = [
        ("detected", "Detected"),    # AI just flagged it (transient)
        ("stored", "Stored"),        # persisted in DB, not yet reviewed
        ("reviewed", "Reviewed"),    # admin has opened/examined it
        ("completed", "Completed"),  # admin finalized (approved)
        ("rejected", "Rejected"),    # admin rejected / false positive
    ]

    VIOLATION_TYPE_CHOICES = [
        ("no_helmet", "No Helmet"),
        ("no_seatbelt", "No Seatbelt"),
        ("red_light", "Red Light"),
        ("over_speed", "Over Speed"),
        ("illegal_parking", "Illegal Parking"),
        ("other", "Other"),
    ]

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="violations"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name="violations"
    )
    violation_type = models.CharField(
        max_length=32, choices=VIOLATION_TYPE_CHOICES, default="no_helmet"
    )
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="stored")
    # v2: estimated speed in km/h (only set for over_speed violations; 0 otherwise)
    speed_kmh = models.FloatField(default=0.0, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vehicle.plate_number} - {self.violation_type} ({self.status})"

    @property
    def evidence_url(self):
        """Return first evidence image URL if any (kept for API backwards-compat)."""
        ev = self.evidence.first()
        return ev.image_url if ev else ""


class Evidence(models.Model):
    """Image evidence for a violation. A violation can have several frames."""
    violation = models.ForeignKey(
        Violation, on_delete=models.CASCADE, related_name="evidence"
    )
    image_path = models.CharField(max_length=255)  # relative to MEDIA_URL, e.g. "/media/violations/abc.jpg"
    capture_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["capture_time"]

    @property
    def image_url(self):
        return self.image_path

    def __str__(self):
        return self.image_path
