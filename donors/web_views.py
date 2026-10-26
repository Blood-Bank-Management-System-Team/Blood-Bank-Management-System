from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.generic import FormView

from users.models import User
from users.web_views import RoleDashboardView

from .forms import DonorProfileForm, RecordDonationForm
from .models import DonationRecord, DonorProfile


class DonorDashboardView(RoleDashboardView):
    template_name = "donors/dashboard.html"
    required_role = User.Role.DONOR

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = DonorProfile.objects.filter(user=self.request.user).first()
        context["profile"] = profile
        context["eligibility"] = profile.eligibility() if profile else None
        donations = profile.donations.all() if profile else DonationRecord.objects.none()
        context["donations"] = donations
        context["donation_count"] = donations.count()
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


class StaffDashboardView(RoleDashboardView):
    template_name = "users/staff_dashboard.html"
    required_role = User.Role.STAFF

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("donation_form", RecordDonationForm())
        return context

    def post(self, request, *args, **kwargs):
        form = RecordDonationForm(request.POST)
        context_kwargs = {"donation_form": form}
        if form.is_valid():
            donor = form.cleaned_data["donor"]
            result = donor.eligibility()
            if not result.eligible:
                form.add_error(None, "Donor is not eligible: " + " ".join(result.reasons))
            else:
                DonationRecord.objects.create(
                    donor=donor,
                    donation_date=form.cleaned_data["donation_date"],
                    blood_bank_location=form.cleaned_data["blood_bank_location"],
                    units=form.cleaned_data["units"],
                    notes=form.cleaned_data["notes"],
                    recorded_by=request.user,
                )
                messages.success(request, f"Donation recorded for {donor.user.username}.")
                return redirect("dashboard-staff")
        return self.render_to_response(self.get_context_data(**context_kwargs))
