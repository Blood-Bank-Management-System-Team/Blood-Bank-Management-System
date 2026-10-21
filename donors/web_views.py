from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.generic import FormView

from users.models import User
from users.web_views import RoleDashboardView

from .forms import DonorProfileForm
from .models import DonorProfile


class DonorDashboardView(RoleDashboardView):
    template_name = "donors/dashboard.html"
    required_role = User.Role.DONOR

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = DonorProfile.objects.filter(user=self.request.user).first()
        context["profile"] = profile
        context["eligibility"] = profile.eligibility() if profile else None
        return context


class DonorProfileFormView(LoginRequiredMixin, FormView):
    form_class = DonorProfileForm
    template_name = "donors/profile.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.DONOR:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = DonorProfile.objects.filter(user=self.request.user).first()
        return kwargs

    def form_valid(self, form):
        profile = form.save(commit=False)
        profile.user = self.request.user
        profile.save()
        return redirect("dashboard-donor")
