from django.contrib import admin

from .models import CampRegistration, DonationCamp


class CampRegistrationInline(admin.TabularInline):
    model = CampRegistration
    extra = 0
    readonly_fields = ("registered_at",)


@admin.register(DonationCamp)
class DonationCampAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "date",
        "venue",
        "available_slots",
        "is_published",
        "created_by",
    )
    list_filter = ("is_published", "date")
    search_fields = ("name", "venue")
    date_hierarchy = "date"
    inlines = (CampRegistrationInline,)


@admin.register(CampRegistration)
class CampRegistrationAdmin(admin.ModelAdmin):
    list_display = ("camp", "donor", "registered_at")
    list_filter = ("camp__date",)
    search_fields = ("camp__name", "donor__user__username")
    readonly_fields = ("registered_at",)