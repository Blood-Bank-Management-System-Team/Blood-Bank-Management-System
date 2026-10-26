from django import forms

from django.db.models import Q

from .models import DonationRecord, DonorProfile, not_in_future


class DonorProfileForm(forms.ModelForm):
    class Meta:
        model = DonorProfile
        fields = (
            "blood_group",
            "date_of_birth",
            "weight_kg",
            "gender",
            "address",
            "city",
            "last_donation_date",
            "has_chronic_illness",
            "on_medication",
            "recent_surgery_or_tattoo_6_months",
            "recent_illness_or_fever_2_weeks",
            "is_pregnant_or_breastfeeding",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "last_donation_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "weight_kg": "Weight (kg)",
            "has_chronic_illness": "I have a chronic illness",
            "on_medication": "I am currently on medication",
            "recent_surgery_or_tattoo_6_months": "I had surgery or a tattoo in the last 6 months",
            "recent_illness_or_fever_2_weeks": "I had an illness or fever in the last 2 weeks",
            "is_pregnant_or_breastfeeding": "I am pregnant or breastfeeding",
        }


class RecordDonationForm(forms.Form):
    donor_query = forms.CharField(label="Donor username or phone")
    donation_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), validators=[not_in_future]
    )
    blood_bank_location = forms.CharField(max_length=200, label="Location")
    units = forms.IntegerField(min_value=1, max_value=2, initial=1)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean_donor_query(self):
        query = self.cleaned_data["donor_query"].strip()
        donors = DonorProfile.objects.select_related("user").filter(
            Q(user__username__iexact=query) | Q(user__phone=query)
        )
        if donors.count() != 1:
            raise forms.ValidationError("No single donor matches that username or phone.")
        self.cleaned_data["donor"] = donors.first()
        return query
