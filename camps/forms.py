
from django import forms
from django.utils import timezone

from .models import DonationCamp


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
            raise forms.ValidationError("At least one slot must be available.")
        return slots
