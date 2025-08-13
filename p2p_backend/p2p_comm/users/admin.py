# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("id","username","email","secondary_email","batch","is_current_student","is_staff")
    fieldsets = UserAdmin.fieldsets + (("Extra", {"fields": ("secondary_email", "batch", "is_current_student")}),)