from django.urls import path

from .web_views import (
    BloodRequestCreatePageView,
    HospitalCancelRequestView,
    MyBloodRequestsPageView,
    ProcessBloodRequestActionView,
    ProcessBloodRequestsPageView,
)

urlpatterns = [
    path("requests/new/", BloodRequestCreatePageView.as_view(), name="blood-request-new"),
    path("requests/mine/", MyBloodRequestsPageView.as_view(), name="blood-request-mine"),
    path(
        "requests/<uuid:request_id>/cancel/",
        HospitalCancelRequestView.as_view(),
        name="blood-request-cancel-page",
    ),
    path("requests/process/", ProcessBloodRequestsPageView.as_view(), name="blood-request-process-page"),
    path(
        "requests/<uuid:request_id>/process/",
        ProcessBloodRequestActionView.as_view(),
        name="blood-request-action",
    ),
]
