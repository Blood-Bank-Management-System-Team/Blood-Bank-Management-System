
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.views.generic import CreateView, TemplateView, UpdateView

from .forms import ProfileForm, RegisterForm
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

    def get_template_names(self):
        role_templates = {
            User.Role.DONOR: "donors/dashboard.html",
            User.Role.STAFF: "users/staff_dashboard.html",
            User.Role.HOSPITAL: "users/hospital_dashboard.html",
            User.Role.ADMIN: "users/admin_dashboard.html",
        }

        return [
            role_templates.get(
                self.required_role,
                self.template_name,
            )
        ]

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.role != self.required_role
        ):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)


class ProfilePageView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = "users/profile.html"

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Profile updated.")
        return redirect("profile")
