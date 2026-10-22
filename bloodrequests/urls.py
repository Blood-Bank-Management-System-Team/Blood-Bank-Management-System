
from django.urls import path

from .views import BloodRequestCreateView, BloodRequestProcessView

urlpatterns = [
    path(
        "",
        BloodRequestCreateView.as_view(),
        name="blood-request-create",
    ),
    path(
        "<uuid:request_id>/process/",
        BloodRequestProcessView.as_view(),
        name="blood-request-process",
    ),
]
