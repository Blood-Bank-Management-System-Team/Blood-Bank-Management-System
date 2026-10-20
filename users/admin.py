from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class BBMSUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (("BBMS", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("BBMS", {"fields": ("role", "phone")}),)
