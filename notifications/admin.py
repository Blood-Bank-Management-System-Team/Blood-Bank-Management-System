from django.contrib import admin
from .models import LowStockThreshold


@admin.register(LowStockThreshold)
class LowStockThresholdAdmin(admin.ModelAdmin):
    list_display = ("blood_group", "minimum_quantity", "updated_at")
    list_editable = ("minimum_quantity",)
    ordering = ("blood_group",)