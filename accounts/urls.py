from django.urls import path

from accounts.views import (
    AdministratorAccountStatusView,
    ChangePasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
    AdministratorRoleApprovalDecisionView,
    AdministratorRoleApprovalListView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfilePhotoView,
    RefreshTokenView,
    RegisterView,
    RoleSelectionView,
    StudentProfileView,
    StudentVerificationConfirmView,
    StudentVerificationResendView,
    StudentVerificationStartView,
)
from accounts.oauth_views import (
    OAuthAuthorizeView,
    OAuthCallbackView,
    OAuthProvidersView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/role-selection/", RoleSelectionView.as_view(), name="auth-role-selection"),
    path(
        "auth/student-email/resend/",
        StudentVerificationResendView.as_view(),
        name="student-email-resend",
    ),
    path(
        "auth/student-email/start/",
        StudentVerificationStartView.as_view(),
        name="student-email-start",
    ),
    path(
        "auth/student-email/verify/",
        StudentVerificationConfirmView.as_view(),
        name="student-email-verify",
    ),
    path(
        "auth/oauth/providers/",
        OAuthProvidersView.as_view(),
        name="oauth-providers",
    ),
    path(
        "auth/oauth/<str:provider>/",
        OAuthAuthorizeView.as_view(),
        name="oauth-authorize",
    ),
    path(
        "auth/oauth/<str:provider>/callback/",
        OAuthCallbackView.as_view(),
        name="oauth-callback",
    ),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("users/me/", CurrentUserView.as_view(), name="current-user"),
    path(
        "users/me/profile-photo/",
        ProfilePhotoView.as_view(),
        name="current-user-profile-photo",
    ),
    path(
        "students/me/profile/",
        StudentProfileView.as_view(),
        name="current-student-profile",
    ),
    path(
        "admin/users/<uuid:user_id>/status/",
        AdministratorAccountStatusView.as_view(),
        name="administrator-user-status",
    ),
    path(
        "admin/role-approvals/",
        AdministratorRoleApprovalListView.as_view(),
        name="administrator-role-approvals",
    ),
    path(
        "admin/role-approvals/<uuid:user_id>/decision/",
        AdministratorRoleApprovalDecisionView.as_view(),
        name="administrator-role-approval-decision",
    ),
]
