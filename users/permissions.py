from rest_framework.permissions import BasePermission

from .models import User


class HasRole(BasePermission):
    """Grants access to authenticated users whose role is in `allowed_roles`."""

    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsDonor(HasRole):
    allowed_roles = (User.Role.DONOR,)


class IsStaff(HasRole):
    allowed_roles = (User.Role.STAFF,)


class IsHospital(HasRole):
    allowed_roles = (User.Role.HOSPITAL,)


class IsAdminRole(HasRole):
    allowed_roles = (User.Role.ADMIN,)


class IsStaffOrAdmin(HasRole):
    allowed_roles = (User.Role.STAFF, User.Role.ADMIN)
