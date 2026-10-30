from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class BBMSUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (("BBMS", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("BBMS", {"fields": ("role", "phone")}),)

from .partner_auth import HospitalPartnerAPIKey


@admin.register(HospitalPartnerAPIKey)
class HospitalPartnerAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key_prefix", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key_prefix")
    readonly_fields = ("key_prefix", "key_hash", "created_at", "last_used_at")