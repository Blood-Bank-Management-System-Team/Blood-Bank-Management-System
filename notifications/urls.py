
from django.urls import path

from .views import LowStockAlertsView

urlpatterns = [
    path(
        "low-stock/",
        LowStockAlertsView.as_view(),
        name="low-stock-alerts",
    ),
]
