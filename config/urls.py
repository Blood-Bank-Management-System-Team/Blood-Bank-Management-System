from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from users.views import health

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("api/health/", health, name="health"),
    path("api/auth/", include("users.urls")),
    path("api/donors/", include("donors.urls")),
    # donors' web URLs come first so its donor dashboard replaces the placeholder one
    path("", include("donors.web_urls")),
    path("", include("users.web_urls")),
    path("admin/", admin.site.urls),
]
