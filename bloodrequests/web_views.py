from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import FormView, ListView

from users.models import User
from users.web_views import RoleRequiredMixin

from .forms import BloodRequestForm
from .models import BloodRequest
from .views import BloodRequestCancelView, BloodRequestProcessView

OPEN_STATUSES = (BloodRequest.RequestStatus.PENDING, BloodRequest.RequestStatus.APPROVED)


def run_api_action(view_class, request, request_id):
    """Run an API view for a web form post, so pages and the API share one workflow.

    The API view re-authenticates through the session and enforces CSRF itself.
    Returns (succeeded, message).
    """
    response = view_class.as_view()(request, request_id=request_id)
    data = getattr(response, "data", None) or {}
    detail = data.get("detail", "") if isinstance(data, dict) else ""
    if 200 <= response.status_code < 300:
        return True, detail
    if "available_units" in data:
        detail = (
            f"{detail} Needed {data['required_units']} unit(s), "
            f"{data['available_units']} compatible unit(s) available."
        )
    return False, detail or "The request could not be updated."


class BloodRequestCreatePageView(RoleRequiredMixin, FormView):
    allowed_roles = (User.Role.HOSPITAL,)
    form_class = BloodRequestForm
    template_name = "bloodrequests/request_form.html"

    def form_valid(self, form):
        form.save(self.request.user)
        messages.success(self.request, "Blood request submitted.")
        return redirect("blood-request-mine")


class MyBloodRequestsPageView(RoleRequiredMixin, ListView):
    allowed_roles = (User.Role.HOSPITAL,)
    template_name = "bloodrequests/my_requests.html"
    context_object_name = "blood_requests"

    def get_queryset(self):
        return BloodRequest.objects.filter(
            requester=self.request.user
        ).order_by("-created_at")


class HospitalCancelRequestView(RoleRequiredMixin, View):
    """Hospital cancels its own approved request, releasing the reserved stock."""

    allowed_roles = (User.Role.HOSPITAL,)

    def post(self, request, request_id):
        ok, detail = run_api_action(BloodRequestCancelView, request, request_id)
        (messages.success if ok else messages.error)(request, detail or "Request cancelled.")
        return redirect("blood-request-mine")


class ProcessBloodRequestsPageView(RoleRequiredMixin, ListView):
    """Staff/admin queue: open requests first, then the most recent closed ones."""

    allowed_roles = (User.Role.STAFF, User.Role.ADMIN)
    template_name = "bloodrequests/process_requests.html"
    context_object_name = "open_requests"

    def get_queryset(self):
        return (
            BloodRequest.objects.filter(status__in=OPEN_STATUSES)
            .select_related("requester")
            .order_by("required_date", "created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["closed_requests"] = (
            BloodRequest.objects.exclude(status__in=OPEN_STATUSES)
            .select_related("requester")
            .order_by("-created_at")[:20]
        )
        return context


class ProcessBloodRequestActionView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.STAFF, User.Role.ADMIN)

    ACTION_MESSAGES = {
        "approved": "Request approved and compatible stock reserved.",
        "rejected": "Request rejected.",
        "fulfilled": "Request marked as fulfilled.",
    }

    def post(self, request, request_id):
        action = request.POST.get("status", "")
        if action == "cancelled":
            ok, detail = run_api_action(BloodRequestCancelView, request, request_id)
        elif action in self.ACTION_MESSAGES:
            ok, detail = run_api_action(BloodRequestProcessView, request, request_id)
            if ok:
                detail = self.ACTION_MESSAGES[action]
        else:
            ok, detail = False, "Unknown action."
        (messages.success if ok else messages.error)(request, detail)
        return redirect("blood-request-process-page")
