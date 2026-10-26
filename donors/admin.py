from django.contrib import admin

from .models import DonationRecord, DonorProfile


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "blood_group", "city", "last_donation_date", "created_at")
    list_filter = ("blood_group", "city")
    search_fields = ("user__username", "city")


@admin.register(DonationRecord)
class DonationRecordAdmin(admin.ModelAdmin):
    list_display = ("donor", "donation_date", "blood_bank_location", "units", "recorded_by")
    list_filter = ("donation_date",)
    search_fields = ("donor__user__username", "blood_bank_location")
