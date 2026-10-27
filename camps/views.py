
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from donors.models import DonorProfile
from users.models import User

from .forms import DonationCampForm
from .models import CampRegistration, DonationCamp


class CampListView(View):
    """Display published donation camps."""

    def get(self, request):
        camps = DonationCamp.objects.filter(
            is_published=True,
            date__gte=timezone.localdate(),
        ).order_by("date", "name")

        return render(
            request,
            "camps/camp_list.html",
            {"camps": camps},
        )


class CampCreateView(LoginRequiredMixin, View):
    """Allow staff and administrators to create donation camps."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in (
            User.Role.STAFF,
            User.Role.ADMIN,
        ):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = DonationCampForm()
        return render(request, "camps/camp_form.html", {"form": form})

    def post(self, request):
        form = DonationCampForm(request.POST)

        if form.is_valid():
            camp = form.save(commit=False)
            camp.created_by = request.user
            camp.save()

            messages.success(
                request,
                "Donation camp created successfully. Publish it to make it visible to donors.",
            )
            return redirect("camp-manage")

        return render(request, "camps/camp_form.html", {"form": form})


class CampManageView(LoginRequiredMixin, View):
    """Allow staff and administrators to view and publish camps."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in (
            User.Role.STAFF,
            User.Role.ADMIN,
        ):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        camps = DonationCamp.objects.all().order_by("-created_at")
        return render(request, "camps/camp_manage.html", {"camps": camps})


class CampPublishView(LoginRequiredMixin, View):
    """Publish or unpublish a camp."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in (
            User.Role.STAFF,
            User.Role.ADMIN,
        ):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        camp = get_object_or_404(DonationCamp, pk=pk)
        camp.is_published = not camp.is_published
        camp.save(update_fields=["is_published", "updated_at"])

        messages.success(
            request,
            "Camp published." if camp.is_published else "Camp unpublished.",
        )
        return redirect("camp-manage")


class CampRegisterView(LoginRequiredMixin, View):
    """Register a donor for a camp while protecting the available slots."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.DONOR:
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        donor = DonorProfile.objects.filter(user=request.user).first()

        if donor is None:
            messages.error(
                request,
                "Please complete your donor profile before registering for a camp.",
            )
            return redirect("donor-profile")

        with transaction.atomic():
            camp = get_object_or_404(
                DonationCamp.objects.select_for_update(),
                pk=pk,
                is_published=True,
                date__gte=timezone.localdate(),
            )

            if CampRegistration.objects.filter(camp=camp, donor=donor).exists():
                messages.info(request, "You are already registered for this camp.")
                return redirect("camp-list")

            registered_count = CampRegistration.objects.filter(camp=camp).count()

            if registered_count >= camp.available_slots:
                messages.error(request, "Sorry, this camp is full.")
                return redirect("camp-list")

            try:
                CampRegistration.objects.create(camp=camp, donor=donor)
            except IntegrityError:
                messages.info(request, "You are already registered for this camp.")
                return redirect("camp-list")

        messages.success(request, f"You have registered for {camp.name}.")
        return redirect("camp-list")
