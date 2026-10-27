from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
import csv

from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from users.permissions import IsAdminRole, IsStaffOrAdmin

from .filters import filter_logs
from . import services
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditLogListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AuditLogSerializer
    pagination_class = AuditLogPagination

    def get_queryset(self):
        try:
            return filter_logs(self.request.query_params)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)


class AuditLogPageView(LoginRequiredMixin, TemplateView):
    template_name = "reports/audit_logs.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.ADMIN:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        error = None
        try:
            qs = filter_logs(params)
        except DjangoValidationError as exc:
            error = "; ".join(f"{k}: {' '.join(v)}" for k, v in exc.message_dict.items())
            qs = AuditLog.objects.none()
        page = Paginator(qs, 25).get_page(params.get("page"))
        keep = params.copy()
        keep.pop("page", None)
        context.update(
            page_obj=page,
            error=error,
            filters=params,
            actions=AuditLog.Action.choices,
            querystring=keep.urlencode(),
        )
        return context


# ---------- BB-17: reports and analytics ----------
def _error_text(exc):
    return "; ".join(" ".join(v) for v in exc.message_dict.values())


class ReportSummaryView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def get(self, request):
        try:
            date_from, date_to = services.parse_date_range(request.query_params)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)
        return Response(services.build_summary(date_from, date_to))


class StaffOrAdminPageMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in (User.Role.ADMIN, User.Role.STAFF):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ReportsPageView(StaffOrAdminPageMixin, TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        error = None
        try:
            date_from, date_to = services.parse_date_range(self.request.GET)
        except DjangoValidationError as exc:
            error = _error_text(exc)
            date_from, date_to = services.parse_date_range({})
        summary = services.build_summary(date_from, date_to)
        donations, stock = summary["donations"], summary["stock"]
        requests_, wastage = summary["requests"], summary["wastage"]
        context.update(
            error=error,
            date_from=date_from,
            date_to=date_to,
            summary=summary,
            has_donations=donations["total_donations"] > 0,
            has_stock=stock["total_units"] > 0,
            has_requests=requests_["total"] > 0,
            has_wastage=wastage["total_units"] > 0,
            chart_data={
                "donations": {
                    "labels": [d["date"] for d in donations["daily"]],
                    "units": [d["units"] for d in donations["daily"]],
                },
                "stock": {
                    "labels": [g["blood_group"] for g in stock["groups"]],
                    "units": [g["units"] for g in stock["groups"]],
                    "low": [g["low_stock"] for g in stock["groups"]],
                },
                "requests": {
                    "labels": [s.capitalize() for s in requests_["by_status"]],
                    "counts": list(requests_["by_status"].values()),
                },
                "wastage": {
                    "labels": list(wastage["by_blood_group"]),
                    "units": list(wastage["by_blood_group"].values()),
                },
            },
        )
        return context


class ReportsCsvExportView(StaffOrAdminPageMixin, View):
    def get(self, request):
        try:
            date_from, date_to = services.parse_date_range(request.GET)
        except DjangoValidationError as exc:
            return HttpResponse(_error_text(exc), status=400, content_type="text/plain")
        s = services.build_summary(date_from, date_to)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="bbms-report-{date_from}-to-{date_to}.csv"'
        w = csv.writer(response)

        def section(title, header, rows):
            w.writerow([title])
            w.writerow(header)
            w.writerows(rows)
            w.writerow([])

        w.writerow(["BBMS report", f"{date_from} to {date_to}"])
        w.writerow([])
        d = s["donations"]
        section("Donations collected", ["Metric", "Value"],
                [["Total units", d["total_units"]], ["Number of donations", d["total_donations"]]])
        section("Donations per day", ["Date", "Donations", "Units"],
                [[r["date"], r["donations"], r["units"]] for r in d["daily"]])
        section("Available stock by blood group (current)", ["Blood group", "Available units", "Minimum", "Low stock"],
                [[g["blood_group"], g["units"], "" if g["minimum"] is None else g["minimum"],
                  "yes" if g["low_stock"] else "no"] for g in s["stock"]["groups"]])
        section("Blood requests by status", ["Status", "Count"], list(s["requests"]["by_status"].items()))
        section("Blood requests by priority", ["Priority", "Count"], list(s["requests"]["by_priority"].items()))
        section("Wastage by blood group", ["Blood group", "Units wasted"], list(s["wastage"]["by_blood_group"].items()))
        section("Wastage by reason", ["Reason", "Units wasted"], list(s["wastage"]["by_reason"].items()))
        return response
