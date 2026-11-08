from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from users.models import User
from users.web_views import RoleRequiredMixin

from .forms import AvailabilitySearchForm, BloodUnitForm
from .models import BloodUnit
from .views import get_available_units


class BloodAvailabilityPageView(RoleRequiredMixin, TemplateView):
    allowed_roles = (User.Role.HOSPITAL, User.Role.STAFF, User.Role.ADMIN)
    template_name = "inventory/availability.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = AvailabilitySearchForm(self.request.GET or None)
        context["form"] = form
        if self.request.GET and form.is_valid():
            context["searched"] = True
            context["blood_group"] = form.cleaned_data["blood_group"]
            context["location"] = form.cleaned_data["location"]
            context["available_units"] = get_available_units(
                form.cleaned_data["blood_group"], form.cleaned_data["location"]
            )
        return context


class InventoryPageView(RoleRequiredMixin, FormView):
    """Staff/admin: list blood units and add new ones."""

    allowed_roles = (User.Role.STAFF, User.Role.ADMIN)
    template_name = "inventory/inventory.html"
    form_class = BloodUnitForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["units"] = BloodUnit.objects.order_by("expiry_date", "blood_group")
        return context

    def form_valid(self, form):
        unit = form.save(commit=False)
        unit.created_by = self.request.user
        unit.updated_by = self.request.user
        unit.save()
        messages.success(
            self.request,
            f"Added {unit.quantity} unit(s) of {unit.blood_group} at {unit.bank_location}.",
        )
        return redirect("inventory-page")
