from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .audit import log_audit
from .models import Organisation, User, Membership
from .serializers import UserSerializer, MembershipSerializer, OrganisationSerializer


def _tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        full_name = request.data.get("full_name", "")
        phone = request.data.get("phone", "")
        if not email or not password:
            return Response({"detail": "email and password are required"}, status=400)
        if len(password) < 8:
            return Response({"detail": "Password must be at least 8 characters"}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({"detail": "Email already registered"}, status=400)
        user = User.objects.create_user(email=email, password=password, full_name=full_name, phone=phone)
        return Response(UserSerializer(user).data, status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=401)
        return Response(_tokens(user))


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("refresh", "")
        try:
            refresh = RefreshToken(token)
            return Response({"access": str(refresh.access_token)})
        except Exception:
            return Response({"detail": "Invalid refresh token"}, status=401)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = UserSerializer(user).data
        data["memberships"] = MembershipSerializer(user.memberships.select_related("organisation"), many=True).data
        return Response(data)


class OrganisationRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        d = request.data
        required = ["name", "admin_name", "admin_email", "admin_password"]
        missing = [f for f in required if not d.get(f)]
        if missing:
            return Response({"detail": f"Missing fields: {', '.join(missing)}"}, status=400)
        admin_email = d["admin_email"].strip().lower()
        if User.objects.filter(email=admin_email).exists():
            return Response({"detail": "Admin email already registered"}, status=400)
        if len(d["admin_password"]) < 8:
            return Response({"detail": "Admin password must be at least 8 characters"}, status=400)
        org = Organisation.objects.create(
            name=d["name"], type=d.get("type", "other"), city=d.get("city", ""),
            email=d.get("email", ""), phone=d.get("phone", ""),
        )
        admin = User.objects.create_user(
            email=admin_email, password=d["admin_password"], full_name=d["admin_name"],
            phone=d.get("phone", ""),
        )
        Membership.objects.create(user=admin, organisation=org, role="org_admin")
        log_audit(actor=admin, organisation=org, action="org_registered",
                  object_type="Organisation", object_id=org.id,
                  detail=f"Organisation '{org.name}' registered by {admin.email}")
        return Response({
            "organisation": OrganisationSerializer(org).data,
            "admin_user": UserSerializer(admin).data,
        }, status=201)


class OrganisationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_platform_admin or request.user.is_superuser):
            return Response({"detail": "Platform admin only"}, status=403)
        orgs = Organisation.objects.all()
        return Response(OrganisationSerializer(orgs, many=True).data)


class PasswordResetView(APIView):
    """POST /auth/password-reset/ {email} — always 200 (no user enumeration).

    Creates a Django default-token-generator token and emails a reset
    link (console backend in dev). In DEBUG the uid/token are also
    returned in the response body so the flow is testable without a
    mailbox; they are never returned when DEBUG is off.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "email is required"}, status=400)
        user = User.objects.filter(email=email, is_active=True).first()
        payload = {"detail": "If that email is registered, a reset link has been sent."}
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
            send_mail(
                subject="SmartCommute password reset",
                message=(
                    f"Hi {user.full_name or user.email},\n\n"
                    f"Reset your SmartCommute password using this link:\n{reset_url}\n\n"
                    f"uid: {uid}\ntoken: {token}\n\n"
                    "If you did not request this, ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            if settings.DEBUG:
                payload["uid"] = uid
                payload["token"] = token
                payload["reset_url"] = reset_url
        return Response(payload)


class PasswordResetConfirmView(APIView):
    """POST /auth/password-reset/confirm/ {uid, token, new_password}."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        new_password = request.data.get("new_password") or ""
        if not uid or not token or not new_password:
            return Response({"detail": "uid, token and new_password are required"}, status=400)
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"detail": "Invalid reset link"}, status=400)
        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired reset token"}, status=400)
        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=400)
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password has been reset. You can now log in."})
