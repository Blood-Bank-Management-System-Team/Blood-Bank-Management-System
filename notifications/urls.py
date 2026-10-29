from django.urls import path

from .views import EmergencyBroadcastView, LowStockAlertsView

urlpatterns = [
    path(
        "low-stock/",
        LowStockAlertsView.as_view(),
        name="low-stock-alerts",
    ),
    path(
        "emergency-broadcast/",
        EmergencyBroadcastView.as_view(),
        name="emergency-broadcast",
    ),
]