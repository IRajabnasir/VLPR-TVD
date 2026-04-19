"""Authentication endpoints: login, refresh, and current-user info."""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView  # re-exported

User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Accepts {"username": "...", "password": "..."} and returns access+refresh tokens."""
    username = (request.data.get("username") or request.data.get("email") or "").strip()
    password = request.data.get("password") or ""

    if not username or not password:
        return Response(
            {"detail": "username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Allow login by either username or email
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User.objects.filter(email__iexact=username).first()

    if user is None or not user.check_password(password) or not user.is_active:
        return Response(
            {"detail": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    u = request.user
    return Response(
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_staff": u.is_staff,
        }
    )


__all__ = ["login_view", "me_view", "TokenRefreshView"]
