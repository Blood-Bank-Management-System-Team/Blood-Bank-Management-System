from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User
from .serializers import SELF_REGISTER_ROLES


class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[(r.value, r.label) for r in SELF_REGISTER_ROLES],
        initial=User.Role.DONOR,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone", "role")
