from django.urls import path

from .views import AuditLogPageView, ReportsCsvExportView, ReportsPageView

urlpatterns = [
    path("reports/", ReportsPageView.as_view(), name="reports"),
    path("reports/export.csv", ReportsCsvExportView.as_view(), name="reports-export"),
    path("reports/audit/", AuditLogPageView.as_view(), name="audit-logs"),
]
