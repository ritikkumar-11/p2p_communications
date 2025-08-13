# users/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail

from .serializers import RegistrationSerializer, CompleteProfileSerializer
from .utils import make_username_from_email, make_random_password

User = get_user_model()

class RegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

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

class CompleteProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CompleteProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.secondary_email = serializer.validated_data["secondary_email"]
        user.batch = serializer.validated_data["batch"]
        user.is_current_student = serializer.validated_data["is_current_student"]
        user.save()
        return Response({"detail":"Profile updated"}, status=status.HTTP_200_OK)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset: list and retrieve users (admins can expand).
    """
    queryset = User.objects.all()
    serializer_class = None  # we'll return basic dicts for brevity

    def list(self, request):
        # minimal user list for admins
        if not request.user.is_staff:
            return Response({"detail":"Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        qs = self.get_queryset()
        data = [{"id":u.id, "username":u.username, "email":u.email, "secondary_email":u.secondary_email, "batch":u.batch, "is_current_student":u.is_current_student} for u in qs]
        return Response(data)
    
    def retrieve(self, request, pk=None):
        try:
            u = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.user.is_staff or request.user.pk == u.pk:
            data = {"id":u.id, "username":u.username, "email":u.email, "secondary_email":u.secondary_email, "batch":u.batch, "is_current_student":u.is_current_student}
            return Response(data)
        return Response({"detail":"Not allowed"}, status=status.HTTP_403_FORBIDDEN)
