
from django.urls import path

from .views import (
    CampCreateView,
    CampListView,
    CampManageView,
    CampPublishView,
    CampRegisterView,
)

urlpatterns = [
    path("camps/", CampListView.as_view(), name="camp-list"),
    path("camps/create/", CampCreateView.as_view(), name="camp-create"),
    path("camps/manage/", CampManageView.as_view(), name="camp-manage"),
    path(
        "camps/<int:pk>/publish/",
        CampPublishView.as_view(),
        name="camp-publish",
    ),
    path(
        "camps/<int:pk>/register/",
        CampRegisterView.as_view(),
        name="camp-register",
    ),
]
