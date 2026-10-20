from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.generic import CreateView, TemplateView

from .forms import RegisterForm
from .models import User

ROLE_DASHBOARDS = {
    User.Role.DONOR: "dashboard-donor",
    User.Role.STAFF: "dashboard-staff",
    User.Role.HOSPITAL: "dashboard-hospital",
    User.Role.ADMIN: "dashboard-admin",
}


class RegisterPageView(CreateView):
    form_class = RegisterForm
    template_name = "users/register.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect("dashboard")


class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect(ROLE_DASHBOARDS[request.user.role])


class RoleDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "users/dashboard.html"
    required_role = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != self.required_role:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
