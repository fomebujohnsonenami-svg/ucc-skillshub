from rest_framework.permissions import BasePermission

from accounts.models import EmployerProfile, RoleApproval, User


def is_opportunity_manager(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.role == User.Role.ADMINISTRATOR:
        return True
    if user.role == User.Role.EMPLOYER:
        return EmployerProfile.objects.filter(user=user).exists()
    if user.role == User.Role.RECRUITER:
        return (
            EmployerProfile.objects.filter(user=user).exists()
            and RoleApproval.objects.filter(
                user=user, status=RoleApproval.Status.APPROVED
            ).exists()
        )
    return False


class IsOpportunityManager(BasePermission):
    def has_permission(self, request, view):
        return is_opportunity_manager(request.user)
