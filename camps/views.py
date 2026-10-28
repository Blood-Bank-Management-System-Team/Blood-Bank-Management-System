from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from donors.models import DonationRecord, DonorProfile
from inventory.models import BloodUnit
from users.models import User

from .forms import CampDonationForm, DonationCampForm
from .models import CampDonation, CampRegistration, DonationCamp


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

        return render(
            request,
            "camps/camp_manage.html",
            {"camps": camps},
        )


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
    """Register a donor for a camp while protecting available slots."""

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

            if CampRegistration.objects.filter(
                camp=camp,
                donor=donor,
            ).exists():
                messages.info(
                    request,
                    "You are already registered for this camp.",
                )
                return redirect("camp-list")

            registered_count = CampRegistration.objects.filter(
                camp=camp,
            ).count()

            if registered_count >= camp.available_slots:
                messages.error(request, "Sorry, this camp is full.")
                return redirect("camp-list")

            try:
                CampRegistration.objects.create(
                    camp=camp,
                    donor=donor,
                )
            except IntegrityError:
                messages.info(
                    request,
                    "You are already registered for this camp.",
                )
                return redirect("camp-list")

        messages.success(request, f"You have registered for {camp.name}.")
        return redirect("camp-list")

class CampDonationRecordView(LoginRequiredMixin, View):
    """Record a camp donation and update inventory and donor history."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.role not in (User.Role.STAFF, User.Role.ADMIN):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        camp = get_object_or_404(DonationCamp, pk=pk)
        form = CampDonationForm(camp=camp)
        return render(
            request,
            "camps/camp_donation_form.html",
            {"form": form, "camp": camp},
        )

    def post(self, request, pk):
        camp = get_object_or_404(DonationCamp, pk=pk)
        form = CampDonationForm(request.POST, camp=camp)

        if not form.is_valid():
            return render(
                request,
                "camps/camp_donation_form.html",
                {"form": form, "camp": camp},
            )

        registration = form.cleaned_data["registration"]
        units = form.cleaned_data["units_collected"]

        try:
            with transaction.atomic():
                registration = CampRegistration.objects.select_for_update().get(
                    pk=registration.pk,
                    camp=camp,
                )

                donation = CampDonation.objects.create(
                    registration=registration,
                    units_collected=units,
                    recorded_by=request.user,
                )

                donor = registration.donor
                collection_date = timezone.localdate()
                expiry_date = collection_date + timedelta(days=35)

                for _ in range(units):
                    BloodUnit.objects.create(
                        blood_group=donor.blood_group,
                        quantity=1,
                        collection_date=collection_date,
                        expiry_date=expiry_date,
                        bank_location=camp.venue,
                        created_by=request.user,
                    )

                DonationRecord.objects.create(
                    donor=donor,
                    donation_date=collection_date,
                    blood_bank_location=camp.venue,
                    units=units,
                    recorded_by=request.user,
                    notes=f"Donation recorded at camp: {camp.name}",
                )

        except IntegrityError:
            messages.error(
                request,
                "This donor's donation has already been recorded for this camp.",
            )
            return redirect("camp-manage")

        messages.success(
            request,
            f"Recorded {units} unit(s) for {registration.donor}.",
        )
        return redirect("camp-manage")