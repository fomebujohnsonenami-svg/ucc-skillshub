from rest_framework.permissions import BasePermission

from accounts.models import User


class HasRole(BasePermission):
    allowed_role = None

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == self.allowed_role
            and request.user.is_active
        )


class IsStudent(HasRole):
    allowed_role = User.Role.STUDENT

    # Student access is based on the active student role, not email verification.


class IsLecturer(HasRole):
    allowed_role = User.Role.LECTURER

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role
            in {User.Role.LECTURER, User.Role.FACILITATOR}
            and request.user.is_active
        )


class IsFacilitator(IsLecturer):
    pass


class IsRecruiter(HasRole):
    allowed_role = User.Role.RECRUITER


class IsAdministrator(HasRole):
    allowed_role = User.Role.ADMINISTRATOR
