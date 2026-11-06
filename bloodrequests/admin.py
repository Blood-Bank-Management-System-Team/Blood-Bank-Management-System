from django.contrib import admin

from .models import BloodRequest, BloodReservation


@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = ("request_id", "requester", "blood_group", "units", "location", "priority", "status", "created_at")
    list_filter = ("status", "priority", "blood_group")
    search_fields = ("request_id", "location", "requester__username")


@admin.register(BloodReservation)
class BloodReservationAdmin(admin.ModelAdmin):
    list_display = ("blood_request", "blood_stock", "units", "active", "created_at", "released_at", "consumed_at")
    list_filter = ("active",)
