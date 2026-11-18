from rest_framework.permissions import BasePermission, IsAuthenticated

from accounts.models import User


class IsActiveStudent(IsAuthenticated):
    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and request.user.role == User.Role.STUDENT
            and request.user.is_active
            and request.user.student_email_verified
        )


class IsPathwayStaff(IsAuthenticated):
    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and request.user.role
            in {
                User.Role.LECTURER,
                User.Role.FACILITATOR,
                User.Role.ADMINISTRATOR,
            }
            and request.user.is_active
        )
