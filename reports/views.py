from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.views.generic import TemplateView
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from users.models import User
from users.permissions import IsAdminRole

from .filters import filter_logs
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
