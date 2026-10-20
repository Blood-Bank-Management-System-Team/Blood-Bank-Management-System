from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from users.views import health

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("api/health/", health, name="health"),
    path("admin/", admin.site.urls),
]
