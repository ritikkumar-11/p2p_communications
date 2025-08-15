# users/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail

from .serializers import RegistrationSerializer, ProfileSerializer
from .models import Profile
from .utils import make_username_from_email, make_random_password
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.generics import RetrieveAPIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from django.http import HttpResponse, Http404

User = get_user_model()

class RegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Register a new student (college email required)",
        description="Create a student account using only the college email. "
                    "The server generates a username and password and emails credentials to the college email.",
        request=RegistrationSerializer,
        responses={
            201: OpenApiResponse(description="Registered. Credentials emailed to college email."),
            400: OpenApiResponse(description="Validation error")
        },
        tags=["Auth"],
        examples=[
            OpenApiExample(
                "Example request",
                value={"college_email": "student@iiitbh.ac.in", "batch": "2025", "is_current_student": True},
                request_only=True,
                response_only=False,
            )
        ],
    )
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        college_email = serializer.validated_data["college_email"]
        batch = serializer.validated_data.get("batch", "")
        is_current = serializer.validated_data.get("is_current_student", True)

        # Generate username and password
        username = make_username_from_email(college_email)
        password = make_random_password()

        # Create user
        user = User.objects.create_user(username=username, email=college_email)
        user.set_password(password)
        user.batch = batch
        user.is_current_student = is_current
        user.save()

        # Email credentials to college email (console backend in dev)
        send_mail(
            subject="Your P2PComm credentials",
            message=f"Hello,\n\nYour account has been created.\n\nUsername: {username}\nPassword: {password}\n\nPlease login at /login/ and complete your profile by adding a secondary email.\n",
            from_email=None,
            recipient_list=[college_email],
            fail_silently=False,
        )

        # Return 201 with location pointing to login page (frontend handles redirect)
        return Response(
            {"detail": "Registered. Credentials emailed to your college email."},
            status=status.HTTP_201_CREATED,
            headers={"Location": "/api/auth/login/"}
        )

# class CompleteProfileView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         serializer = CompleteProfileSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = request.user
#         user.secondary_email = serializer.validated_data["secondary_email"]
#         user.batch = serializer.validated_data["batch"]
#         user.is_current_student = serializer.validated_data["is_current_student"]
#         user.save()
#         return Response({"detail":"Profile updated"}, status=status.HTTP_200_OK)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset: list and retrieve users (admins can expand).
    """
    queryset = User.objects.all()
    serializer_class = None  # we'll return basic dicts for brevity

    @extend_schema(
        summary="List users (admin only)",
        description="Return a list of users. Accessible only to staff accounts.",
        responses={200: OpenApiResponse(description="List of users"), 403: OpenApiResponse(description="Not allowed")},
        tags=["Users"],
    )
    def list(self, request):
        # minimal user list for admins
        if not request.user.is_staff:
            return Response({"detail":"Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        qs = self.get_queryset()
        data = [{"id":u.id, "username":u.username, "email":u.email, "secondary_email":u.secondary_email, "batch":u.batch, "is_current_student":u.is_current_student} for u in qs]
        return Response(data)
    
    @extend_schema(
        summary="Retrieve user (self or admin)",
        description="Retrieve a single user's basic info. Admins can fetch any user; regular users only their own record.",
        responses={200: OpenApiResponse(description="User object"), 403: OpenApiResponse(description="Not allowed"), 404: OpenApiResponse(description="Not found")},
        parameters=[OpenApiParameter(name="pk", description="User primary key", required=True, type=int)],
        tags=["Users"],
    )
    
    def retrieve(self, request, pk=None):
        try:
            u = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.user.is_staff or request.user.pk == u.pk:
            data = {"id":u.id, "username":u.username, "email":u.email, "secondary_email":u.secondary_email, "batch":u.batch, "is_current_student":u.is_current_student}
            return Response(data)
        return Response({"detail":"Not allowed"}, status=status.HTTP_403_FORBIDDEN)


class MeProfileView(APIView):
    """
    GET  /api/profile/me/     -> current user's profile
    PATCH /api/profile/me/    -> update current user's profile
    Accepts JSON or multipart (for avatar)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Get current user's profile",
        description="Returns the authenticated user's profile.",
        responses={200: ProfileSerializer},
        tags=["Profile"]
    )
    def get(self, request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(profile)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update current user's profile",
        description="Partial update to profile (PATCH). Supports multipart for avatar or base64 payload.",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
        tags=["Profile"]
    )
    def patch(self, request, *args, **kwargs):
        serializer = ProfileSerializer(
            request.user.profile, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PublicProfileView(RetrieveAPIView):
    """
    GET /api/profile/<username>/
    Public read-only view for profiles (no sensitive fields like emails if you want)
    """
    permission_classes = [AllowAny]
    serializer_class = ProfileSerializer
    lookup_field = "username"

    @extend_schema(
        summary="Get public profile by username",
        description="Public profile data (omits private fields).",
        responses={200: ProfileSerializer},
        parameters=[OpenApiParameter(name="username", description="username", required=True, type=str)],
        tags=["Profile"]
    )
    def get_object_or_404(self):
        username = self.kwargs.get("username")
        user = get_object_or_404(User, username=username)
        profile, _ = Profile.objects.get_or_create(user=user)
        # Optionally redact fields for public view (e.g., hide secondary_email)
        return profile
    
class PublicProfileView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProfileSerializer
    lookup_field = "username"

    @extend_schema(
        summary="Get public profile by username",
        description="Public profile data (omits private fields).",
        responses={200: ProfileSerializer},
        parameters=[OpenApiParameter(name="username", description="username", required=True, type=str)],
        tags=["Profile"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# Serve avatar binary from DB. Public or protected depending on your policy (here we keep public)
@extend_schema(
    summary="Get user's avatar image",
    description="Returns the avatar image bytes with proper Content-Type.",
    responses={200: OpenApiResponse(description="image bytes")},
    tags=["Profile"]
)
def profile_avatar_view(request, username):
    user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=user)
    if not profile.has_avatar():
        raise Http404("No avatar")
    content = profile.avatar_blob
    ct = profile.avatar_content_type or "application/octet-stream"
    resp = HttpResponse(content, content_type=ct)
    # optionally set Content-Disposition if you want it downloaded:
    # resp['Content-Disposition'] = f'inline; filename="{profile.avatar_filename}"'
    return resp
