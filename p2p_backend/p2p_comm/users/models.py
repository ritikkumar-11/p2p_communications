# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    # keep first_name, last_name, username fields from AbstractUser
    email = models.EmailField(unique=True)
    secondary_email = models.EmailField(blank=True, null=True)
    batch = models.CharField(max_length=10, blank=True)  # e.g., "2022"
    is_current_student = models.BooleanField(default=True)  # True=current, False=alumni

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username
