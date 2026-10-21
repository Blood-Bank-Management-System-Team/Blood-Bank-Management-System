
from django.urls import path

from .views import (
    BloodUnitListCreateView,
    BloodUnitDetailView,
    StockSummaryView,
)

urlpatterns = [
    path("", BloodUnitListCreateView.as_view(), name="blood-unit-list-create"),
    path("stock-summary/", StockSummaryView.as_view(), name="stock-summary"),
    path("<int:pk>/", BloodUnitDetailView.as_view(), name="blood-unit-detail"),
]
