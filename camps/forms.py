from django import forms
from django.utils import timezone

from .models import CampDonation, CampRegistration, DonationCamp


class DonationCampForm(forms.ModelForm):
    class Meta:
        model = DonationCamp
        fields = ["name", "description", "date", "venue", "available_slots"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_date(self):
        camp_date = self.cleaned_data["date"]
        if camp_date < timezone.localdate():
            raise forms.ValidationError("Camp date cannot be in the past.")
        return camp_date

    def clean_available_slots(self):
        slots = self.cleaned_data["available_slots"]
        if slots < 1:
            raise forms.ValidationError(
                "At least one slot must be available."
            )
        return slots


class CampDonationForm(forms.ModelForm):
    class Meta:
        model = CampDonation
        fields = ["registration", "units_collected"]

    def __init__(self, *args, camp=None, **kwargs):
        super().__init__(*args, **kwargs)

        if camp is not None:
            self.fields["registration"].queryset = (
                CampRegistration.objects
                .filter(
                    camp=camp,
                    donation_record__isnull=True,
                )
                .select_related("donor__user")
                .order_by("donor__user__username")
            )

    def clean_units_collected(self):
        units = self.cleaned_data["units_collected"]

        if not 1 <= units <= 2:
            raise forms.ValidationError(
                "The number of collected units must be between 1 and 2."
            )

        return units