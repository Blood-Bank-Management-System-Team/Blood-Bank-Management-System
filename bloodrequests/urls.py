from django.urls import path

from .views import (
    BloodRequestCreateView,
    BloodRequestListView,
    BloodRequestProcessView,
    BloodRequestCancelView,
)

urlpatterns = [
    path("", BloodRequestCreateView.as_view(), name="blood-request-create"),
    path("list/", BloodRequestListView.as_view(), name="blood-request-list"),
    path(
        "<uuid:request_id>/process/",
        BloodRequestProcessView.as_view(),
        name="blood-request-process",
    ),
    path(
        "<uuid:request_id>/cancel/",
        BloodRequestCancelView.as_view(),
        name="blood-request-cancel",
    ),
]