# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

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

class CompleteProfileSerializer(serializers.Serializer):
    secondary_email = serializers.EmailField()
    batch = serializers.CharField(max_length=10)
    is_current_student = serializers.BooleanField()

    def validate_secondary_email(self, value):
        if value.lower().endswith(COLLEGE_DOMAIN):
            raise serializers.ValidationError("Secondary email must be a non-college personal email.")
        return value.lower()
