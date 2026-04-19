from django.contrib import admin
from .models import Camera, Vehicle, LicensePlate, Violation, Evidence


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "location", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "location")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("id", "plate_number", "vehicle_type", "color", "owner_name")
    search_fields = ("plate_number", "owner_name")


@admin.register(LicensePlate)
class LicensePlateAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "plate_number", "confidence_score", "created_at")
    search_fields = ("plate_number",)


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 0
    readonly_fields = ("image_path", "capture_time")


@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "camera", "violation_type", "fine_amount", "status", "created_at")
    list_filter = ("status", "violation_type")
    search_fields = ("vehicle__plate_number", "location")
    inlines = [EvidenceInline]


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("id", "violation", "image_path", "capture_time")
    search_fields = ("image_path",)
