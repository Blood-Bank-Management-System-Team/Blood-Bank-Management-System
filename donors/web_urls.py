from django.urls import path

from .web_views import DonationCertificateView, DonorDashboardView, DonorProfileFormView, StaffDashboardView

urlpatterns = [
    path("dashboard/donor/", DonorDashboardView.as_view(), name="dashboard-donor"),
    path("dashboard/staff/", StaffDashboardView.as_view(), name="dashboard-staff"),
    path("donors/donations/<int:pk>/certificate/", DonationCertificateView.as_view(), name="donation-certificate"),
    path("donors/profile/", DonorProfileFormView.as_view(), name="donor-profile"),
]
