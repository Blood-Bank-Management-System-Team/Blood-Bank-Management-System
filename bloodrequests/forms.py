from django import forms

from .models import BloodRequest
from .serializers import BloodRequestSerializer


class BloodRequestForm(forms.Form):
    blood_group = forms.ChoiceField(choices=BloodRequest.BloodGroup.choices)
    units = forms.IntegerField(min_value=1)
    location = forms.CharField(max_length=100, label="Location")
    priority = forms.ChoiceField(choices=BloodRequest.Priority.choices)
    required_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Required date (scheduled requests)",
    )

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        # Same validation as the API (e.g. scheduled requests need a future date).
        self.serializer = BloodRequestSerializer(data={
            "blood_group": cleaned["blood_group"],
            "units": cleaned["units"],
            "location": cleaned["location"],
            "priority": cleaned["priority"],
            "required_date": cleaned.get("required_date"),
        })
        if not self.serializer.is_valid():
            for field, errors in self.serializer.errors.items():
                for error in errors:
                    self.add_error(field if field in self.fields else None, error)
        return cleaned

    def save(self, requester):
        return self.serializer.save(requester=requester)
