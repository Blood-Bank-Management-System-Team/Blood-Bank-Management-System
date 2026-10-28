
from django.contrib.auth import views as auth_views
from django.urls import path

from .models import User
from .web_views import (
    DashboardRedirectView,
    ProfilePageView,
    RegisterPageView,
    RoleDashboardView,
    password_reset_new_password_view,
    password_reset_request_view,
    password_reset_verify_view,
)

urlpatterns = [
    path("register/", RegisterPageView.as_view(), name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="users/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", ProfilePageView.as_view(), name="profile"),
    path("dashboard/", DashboardRedirectView.as_view(), name="dashboard"),
    path(
        "dashboard/donor/",
        RoleDashboardView.as_view(required_role=User.Role.DONOR),
        name="dashboard-donor",
    ),
    path(
        "dashboard/staff/",
        RoleDashboardView.as_view(required_role=User.Role.STAFF),
        name="dashboard-staff",
    ),
    path(
        "dashboard/hospital/",
        RoleDashboardView.as_view(required_role=User.Role.HOSPITAL),
        name="dashboard-hospital",
    ),
    path(
        "dashboard/admin/",
        RoleDashboardView.as_view(required_role=User.Role.ADMIN),
        name="dashboard-admin",
    ),
    path(
        "password-reset/",
        password_reset_request_view,
        name="password-reset-request",
    ),
    path(
        "password-reset/verify/",
        password_reset_verify_view,
        name="password-reset-verify",
    ),
    path(
        "password-reset/new-password/",
        password_reset_new_password_view,
        name="password-reset-new-password",
    ),
]