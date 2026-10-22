
from django.urls import path

from .views import BloodRequestCreateView

urlpatterns = [
    path(
        "",
        BloodRequestCreateView.as_view(),
        name="blood-request-create",
    ),
]
