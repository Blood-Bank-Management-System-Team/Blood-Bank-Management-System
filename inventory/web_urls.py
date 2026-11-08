from django.urls import path

from .web_views import BloodAvailabilityPageView, InventoryPageView

urlpatterns = [
    path("blood/availability/", BloodAvailabilityPageView.as_view(), name="blood-availability-page"),
    path("inventory/", InventoryPageView.as_view(), name="inventory-page"),
]
