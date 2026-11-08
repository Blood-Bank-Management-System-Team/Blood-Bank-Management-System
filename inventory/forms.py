from django import forms

from .models import BloodStock, BloodUnit


class AvailabilitySearchForm(forms.Form):
    blood_group = forms.ChoiceField(choices=BloodStock.BloodGroup.choices)
    location = forms.CharField(max_length=100)

    def clean_location(self):
        return self.cleaned_data["location"].strip()


class BloodUnitForm(forms.ModelForm):
    class Meta:
        model = BloodUnit
        fields = ("blood_group", "quantity", "collection_date", "expiry_date", "bank_location")
        widgets = {
            "collection_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"quantity": "Units", "bank_location": "Blood bank location"}

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity < 1:
            raise forms.ValidationError("Enter at least 1 unit.")
        return quantity

    def clean_bank_location(self):
        return self.cleaned_data["bank_location"].strip()

    def clean(self):
        cleaned = super().clean()
        collection, expiry = cleaned.get("collection_date"), cleaned.get("expiry_date")
        if collection and expiry and expiry <= collection:
            self.add_error("expiry_date", "Expiry date must be after collection date.")
        return cleaned
