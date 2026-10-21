from django import forms

from .models import DonorProfile


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
