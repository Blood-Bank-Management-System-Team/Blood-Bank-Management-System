from django.contrib import admin

from .models import BloodStock, BloodUnit


@admin.register(BloodUnit)
class BloodUnitAdmin(admin.ModelAdmin):
    list_display = ("id", "blood_group", "quantity", "bank_location", "collection_date", "expiry_date")
    list_filter = ("blood_group", "bank_location")


@admin.register(BloodStock)
class BloodStockAdmin(admin.ModelAdmin):
    list_display = ("id", "blood_group", "location", "available_units", "status", "expiry_date")
    list_filter = ("status", "blood_group", "location")
