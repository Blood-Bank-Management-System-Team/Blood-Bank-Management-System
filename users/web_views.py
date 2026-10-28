
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import CreateView, TemplateView, UpdateView

from inventory.models import BloodUnit
from notifications.models import AdminNotification, LowStockThreshold

from .forms import (
    PasswordResetOTPForm,
    PasswordResetRequestForm,
    ProfileForm,
    RegisterForm,
    SetNewPasswordForm,
)
from .models import User
from .password_reset import (
    consume_password_reset_grant,
    get_password_reset_grant_user,
    request_password_reset,
    verify_password_reset_otp,
)



ROLE_DASHBOARDS = {
    User.Role.DONOR: "dashboard-donor",
    User.Role.STAFF: "dashboard-staff",
    User.Role.HOSPITAL: "dashboard-hospital",
    User.Role.ADMIN: "dashboard-admin",
}


class RegisterPageView(CreateView):
    form_class = RegisterForm
    template_name = "users/register.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect("dashboard")


class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect(ROLE_DASHBOARDS[request.user.role])


class RoleDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "users/dashboard.html"
    required_role = None

    def get_template_names(self):
        role_templates = {
            User.Role.DONOR: "donors/dashboard.html",
            User.Role.STAFF: "users/staff_dashboard.html",
            User.Role.HOSPITAL: "users/hospital_dashboard.html",
            User.Role.ADMIN: "users/admin_dashboard.html",
        }

        return [
            role_templates.get(
                self.required_role,
                self.template_name,
            )
        ]

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.role != self.required_role
        ):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.required_role == User.Role.ADMIN:
            today = timezone.localdate()
            alerts = []

            thresholds = LowStockThreshold.objects.all().order_by(
                "blood_group"
            )

            for threshold in thresholds:
                available_quantity = (
                    BloodUnit.objects.filter(
                        blood_group=threshold.blood_group,
                        expiry_date__gte=today,
                        quantity__gt=0,
                    ).aggregate(total=Sum("quantity"))["total"]
                    or 0
                )

                if available_quantity < threshold.minimum_quantity:
                    alerts.append({
                        "blood_group": threshold.blood_group,
                        "available_quantity": available_quantity,
                        "minimum_quantity": threshold.minimum_quantity,
                    })

            context["low_stock_alerts"] = alerts

            for alert in alerts:
                message = (
                    f"Low stock for {alert['blood_group']}: "
                    f"{alert['available_quantity']} available, "
                    f"minimum is {alert['minimum_quantity']}."
                )

                notification = AdminNotification.objects.filter(
                    blood_group=alert["blood_group"],
                    is_read=False,
                ).order_by("-created_at").first()

                if notification is None:
                    AdminNotification.objects.create(
                        blood_group=alert["blood_group"],
                        message=message,
                        available_quantity=alert["available_quantity"],
                        minimum_quantity=alert["minimum_quantity"],
                    )
                elif (
                    notification.available_quantity
                    != alert["available_quantity"]
                    or notification.minimum_quantity
                    != alert["minimum_quantity"]
                    or notification.message != message
                ):
                    notification.message = message
                    notification.available_quantity = (
                        alert["available_quantity"]
                    )
                    notification.minimum_quantity = (
                        alert["minimum_quantity"]
                    )
                    notification.save(update_fields=[
                        "message",
                        "available_quantity",
                        "minimum_quantity",
                    ])

            context["admin_notifications"] = (
                AdminNotification.objects
                .filter(is_read=False)
                .order_by("-created_at")[:10]
            )

        return context


class ProfilePageView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = "users/profile.html"

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Profile updated.")
        return redirect("profile")

def password_reset_request_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]

            try:
                request_password_reset(email)
            except Exception:
                form.add_error(
                    None,
                    "Unable to send the reset email right now. Please try again.",
                )
            else:
                request.session["password_reset_email"] = email.strip()
                messages.success(
                    request,
                    "If the email is registered, a password-reset OTP has been sent.",
                )
                return redirect("password-reset-verify")
    else:
        form = PasswordResetRequestForm()

    return render(
        request,
        "users/password_reset_request.html",
        {"form": form},
    )


def password_reset_verify_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    email = request.session.get("password_reset_email")

    if not email:
        return redirect("password-reset-request")

    if request.method == "POST":
        form = PasswordResetOTPForm(
            request.POST,
            initial={"email": email},
        )

        if form.is_valid():
            grant = verify_password_reset_otp(
                email,
                form.cleaned_data["otp"],
            )

            if grant:
                request.session["password_reset_grant"] = grant
                return redirect("password-reset-new-password")

            form.add_error("otp", "Invalid or expired OTP. Please try again.")
    else:
        form = PasswordResetOTPForm(initial={"email": email})

    return render(
        request,
        "users/password_reset_verify.html",
        {"form": form},
    )


def password_reset_new_password_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    grant = request.session.get("password_reset_grant")

    if not grant or not get_password_reset_grant_user(grant):
        request.session.pop("password_reset_grant", None)
        return redirect("password-reset-request")

    if request.method == "POST":
        form = SetNewPasswordForm(request.POST)

        if form.is_valid():
            user = consume_password_reset_grant(grant)

            if user is None:
                request.session.pop("password_reset_grant", None)
                form.add_error(
                    None,
                    "Your reset session has expired. Please request a new OTP.",
                )
            else:
                user.set_password(form.cleaned_data["new_password1"])
                user.save(update_fields=["password"])

                request.session.pop("password_reset_grant", None)
                request.session.pop("password_reset_email", None)

                messages.success(
                    request,
                    "Your password has been reset. You can now log in.",
                )
                return redirect("login")
    else:
        form = SetNewPasswordForm()

    return render(
        request,
        "users/password_reset_new_password.html",
        {"form": form},
    )