
from django.urls import path

from .views import BloodAvailabilityView

urlpatterns = [
    path(
        "availability/",
        BloodAvailabilityView.as_view(),
        name="blood-availability",
    ),
]
