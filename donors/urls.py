from django.urls import path

from .views import DonorDonationCreateView, MyDonationsView, DonorEligibilityView, DonorListView, DonorProfileView

urlpatterns = [
    path("", DonorListView.as_view(), name="api-donor-list"),
    path("profile/", DonorProfileView.as_view(), name="api-donor-profile"),
    path("me/donations/", MyDonationsView.as_view(), name="api-my-donations"),
    path("<int:donor_id>/donations/", DonorDonationCreateView.as_view(), name="api-donor-donations"),
    path("eligibility/", DonorEligibilityView.as_view(), name="api-donor-eligibility"),
]
