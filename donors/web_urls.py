from django.urls import path

from .web_views import DonorDashboardView, DonorProfileFormView

urlpatterns = [
    path("dashboard/donor/", DonorDashboardView.as_view(), name="dashboard-donor"),
    path("donors/profile/", DonorProfileFormView.as_view(), name="donor-profile"),
]
