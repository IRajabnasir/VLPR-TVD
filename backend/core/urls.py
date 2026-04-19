from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CameraViewSet, VehicleViewSet, ViolationViewSet
from .api import create_detection
from .views_ai import AnalyzeView
from .views_stats import StatsView
from .auth_views import login_view, me_view, TokenRefreshView

router = DefaultRouter()
router.register("cameras", CameraViewSet)
router.register("vehicles", VehicleViewSet)
router.register("violations", ViolationViewSet)

urlpatterns = [
    # Auth
    path("auth/login/", login_view, name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", me_view, name="auth-me"),

    # AI + detection
    path("analyze/", AnalyzeView.as_view(), name="analyze"),
    path("detections/", create_detection, name="detections-create"),

    # Stats for dashboard
    path("stats/", StatsView.as_view(), name="stats"),
]

urlpatterns += router.urls
