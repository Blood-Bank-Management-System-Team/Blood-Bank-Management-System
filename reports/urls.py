from django.urls import path

from .views import AuditLogListView, ReportSummaryView

urlpatterns = [
    path("audit-logs/", AuditLogListView.as_view(), name="api-audit-logs"),
    path("summary/", ReportSummaryView.as_view(), name="api-report-summary"),
]
