from django.urls import path

from .views import DonorEligibilityView, DonorListView, DonorProfileView

urlpatterns = [
    path("", DonorListView.as_view(), name="api-donor-list"),
    path("profile/", DonorProfileView.as_view(), name="api-donor-profile"),
    path("eligibility/", DonorEligibilityView.as_view(), name="api-donor-eligibility"),
]
