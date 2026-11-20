from accounts.models import RoleApproval, User


def user_authentication_rule(user):
    if not user or not user.is_active:
        return False
    # Student email verification is optional; active students can authenticate.
    if user.role in {User.Role.FACILITATOR, User.Role.RECRUITER}:
        return RoleApproval.objects.filter(
            user=user, status=RoleApproval.Status.APPROVED
        ).exists()
    return True
