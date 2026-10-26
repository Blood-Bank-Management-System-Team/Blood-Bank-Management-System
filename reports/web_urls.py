from django.urls import path

from .views import AuditLogPageView

urlpatterns = [
    path("reports/audit/", AuditLogPageView.as_view(), name="audit-logs"),
]
