from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password

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
from django.contrib.auth.password_validation import validate_password


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Registered email address",
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "Enter your registered email",
        }),
    )


class PasswordResetOTPForm(forms.Form):
    email = forms.EmailField(
        widget=forms.HiddenInput(),
    )
    otp = forms.CharField(
        label="Email OTP",
        min_length=6,
        max_length=6,
        strip=True,
        widget=forms.TextInput(attrs={
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "placeholder": "Enter your 6-digit OTP",
        }),
    )

    def clean_otp(self):
        otp = self.cleaned_data["otp"]

        if not otp.isdigit():
            raise forms.ValidationError("Enter a valid 6-digit OTP.")

        return otp


class SetNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
        }),
        validators=[validate_password],
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")

        if password1 and password2 and password1 != password2:
            self.add_error(
                "new_password2",
                "The passwords do not match.",
            )

        return cleaned_data
