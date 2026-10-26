from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, MeView, ProfileView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="api-register"),
    path("login/", LoginView.as_view(), name="api-login"),
    path("refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("profile/", ProfileView.as_view(), name="api-profile"),
    path("me/", MeView.as_view(), name="api-me"),
]
