# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Profile
from .utils import make_username_from_email
from rest_framework.validators import UniqueValidator
from rest_framework.exceptions import ValidationError
import base64


User = get_user_model()
COLLEGE_DOMAIN = "@iiitbh.ac.in"  # enforce college domain

class RegistrationSerializer(serializers.Serializer):
    college_email = serializers.EmailField()
    batch = serializers.CharField(max_length=10, required=False)
    is_current_student = serializers.BooleanField(default=True)

    def validate_college_email(self, value):
        if not value.lower().endswith(COLLEGE_DOMAIN):
            raise serializers.ValidationError("Registration requires a college email.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this college email already exists.")
        return value.lower()

MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB
ALLOWED_AVATAR_TYPES = ["image/jpeg", "image/png", "image/webp"]

class ProfileSerializer(serializers.ModelSerializer):
    # expose some fields from the user model and allow editing them
    username = serializers.CharField(source="user.username", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)  # college email, read-only
    secondary_email = serializers.EmailField(source="user.secondary_email", required=False, allow_null=True, allow_blank=True)
    batch = serializers.CharField(source="user.batch", required=False, allow_blank=True, allow_null=True)
    is_current_student = serializers.BooleanField(source="user.is_current_student", required=False)
    # For file upload (multipart)
    avatar = serializers.ImageField(write_only=True, required=False, allow_null=True)

    # Or accept base64 string (frontend may use this)
    avatar_base64 = serializers.CharField(write_only=True, required=False, allow_null=True)

    # Expose an avatar URL endpoint for GET (not storing URL, but client can GET /api/profile/me/avatar/)
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "username", "email", "secondary_email",
            "batch", "is_current_student",
            "headline", "about", "location",
            "experiences", "links",
            "avatar", "updated_at",
        ]
        read_only_fields = ["updated_at"]
    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj and obj.has_avatar():
            return request.build_absolute_uri(f"/api/profile/{obj.user.username}/avatar/")
        return None

    def validate(self, data):
        # avatar validation for multipart and base64
        avatar_file = data.get("avatar", None)
        avatar_b64 = data.get("avatar_base64", None)

        if avatar_file:
            ct = getattr(avatar_file, "content_type", None)
            size = getattr(avatar_file, "size", 0)
            if ct not in ALLOWED_AVATAR_TYPES:
                raise serializers.ValidationError({"avatar": "Unsupported avatar file type."})
            if size > MAX_AVATAR_SIZE:
                raise serializers.ValidationError({"avatar": "Avatar too large (max 2MB)."})
        elif avatar_b64:
            # validate base64: decode header if present (data:...;base64,...)
            try:
                if avatar_b64.startswith("data:"):
                    header, b64data = avatar_b64.split(",", 1)
                    content_type = header.split(";")[0].split(":")[1]
                else:
                    b64data = avatar_b64
                    content_type = None
                decoded = base64.b64decode(b64data)
                if len(decoded) > MAX_AVATAR_SIZE:
                    raise serializers.ValidationError({"avatar_base64": "Avatar too large (max 2MB)."})
                if content_type and content_type not in ALLOWED_AVATAR_TYPES:
                    raise serializers.ValidationError({"avatar_base64": "Unsupported avatar file type."})
            except Exception:
                raise serializers.ValidationError({"avatar_base64": "Invalid base64 image."})

        return data

    def update(self, instance, validated_data):
        # handle nested user fields
        user_data = validated_data.pop("user", {})
        user = instance.user
        username = user_data.get("username")
        if username:
            # UniqueValidator already checked uniqueness but ensure update handles same-user case
            if User.objects.exclude(pk=user.pk).filter(username=username).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
            user.username = username

        # other nested fields
        for attr in ("secondary_email", "batch", "is_current_student"):
            if attr in user_data:
                setattr(user, attr, user_data[attr])
        user.save()

        # update profile fields
        return super().update(instance, validated_data)
