
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from users.views import health

urlpatterns = [
    # Home page
    path("", TemplateView.as_view(template_name="home.html"), name="home"),

    # Health check
    path("api/health/", health, name="health"),

    # API URLs
    path("api/auth/", include("users.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/donors/", include("donors.urls")),
    path("api/blood/", include("inventory.urls")),
    path("api/blood-requests/", include("bloodrequests.urls")),
    path("api/inventory/", include("inventory.urls")),

    # Donation camp URLs
    path("", include("camps.urls")),

    # Existing web URLs
    path("", include("donors.web_urls")),
    path("", include("users.web_urls")),
    path("", include("reports.web_urls")),

    # Admin
    path("admin/", admin.site.urls),
    path("api/notifications/", include("notifications.urls")),
   
]
