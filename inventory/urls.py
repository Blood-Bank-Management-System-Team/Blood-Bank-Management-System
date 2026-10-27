from django.urls import path

from .views import (
    BloodAvailabilityView,
    BloodUnitListCreateView,
    BloodUnitDetailView,
    StockSummaryView,
    CrossBankSearchView,
)

urlpatterns = [
    path(
        "availability/",
        BloodAvailabilityView.as_view(),
        name="blood-availability",
    ),
    path(
        "cross-bank-search/",
        CrossBankSearchView.as_view(),
        name="cross-bank-search",
    ),
    path(
        "",
        BloodUnitListCreateView.as_view(),
        name="blood-unit-list-create",
    ),
    path(
        "stock-summary/",
        StockSummaryView.as_view(),
        name="stock-summary",
    ),
    path(
        "<int:pk>/",
        BloodUnitDetailView.as_view(),
        name="blood-unit-detail",
    ),
]