
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminUserDetailView,
    AdminUserListCreateView,
    LoginView,
    MeView,
    ProfileView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="api-register"),
    path("login/", LoginView.as_view(), name="api-login"),
    path("refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("profile/", ProfileView.as_view(), name="api-profile"),
    path("me/", MeView.as_view(), name="api-me"),
    path(
        "admin/users/",
        AdminUserListCreateView.as_view(),
        name="api-admin-users",
    ),
    path(
        "admin/users/<int:pk>/",
        AdminUserDetailView.as_view(),
        name="api-admin-user-detail",
    ),
]
