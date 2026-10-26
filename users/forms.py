from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User
from .serializers import PHONE_RE, SELF_REGISTER_ROLES


class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[(r.value, r.label) for r in SELF_REGISTER_ROLES],
        initial=User.Role.DONOR,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone", "role")


class ProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=False, validators=[PHONE_RE], max_length=10)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")
