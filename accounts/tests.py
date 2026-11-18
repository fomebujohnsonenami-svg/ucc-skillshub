from io import BytesIO
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import (
    OAuthState,
    RoleApproval,
    SocialAccount,
    StudentProfile,
    StudentVerification,
    User,
)

PASSWORD = "V3ry$trong-Password-2026!"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.registration_data = {
            "email": "student@example.edu",
            "first_name": "Ama",
            "last_name": "Mensah",
            "password": PASSWORD,
        }

    def register(self, **overrides):
        registration_overrides = dict(overrides)
        student_email = registration_overrides.pop(
            "student_email", "student@ucc.edu.gh"
        )
        response = self.client.post(
            "/api/v1/auth/register/",
            {**self.registration_data, **registration_overrides},
            format="json",
        )
        if response.status_code == status.HTTP_201_CREATED:
            selected = self.client.post(
                "/api/v1/auth/role-selection/",
                {
                    "onboarding_token": response.data["onboarding_token"],
                    "role": User.Role.STUDENT,
                    "student_email": student_email,
                },
                format="json",
            )
            self.assertEqual(selected.status_code, status.HTTP_200_OK)
            self.onboarding_token = selected.data["onboarding_token"]
        return response

    def activate(self, email="student@example.edu"):
        user = User.objects.get(email=email)
        verification = StudentVerification.objects.get(user=user)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        response = self.client.post(
            "/api/v1/auth/student-email/verify/",
            {"onboarding_token": self.onboarding_token, "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        verification.refresh_from_db()
        self.assertIsNotNone(verification.consumed_at)
        user.refresh_from_db()
        return user

    def login(self, email="student@example.edu"):
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": PASSWORD},
            format="json",
        )

    def test_registration_creates_pending_student_with_hashed_password_and_profile(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(
            user.account_status, User.AccountStatus.PENDING_STUDENT_VERIFICATION
        )
        self.assertFalse(user.is_active)
        self.assertEqual(user.student_email, "student@ucc.edu.gh")
        self.assertFalse(user.student_email_verified)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        self.assertEqual(response.data["user"]["role"], "")
        self.assertNotIn("code", response.data)
        self.assertEqual(mail.outbox[-1].to, ["student@ucc.edu.gh"])

    def test_registration_rejects_client_supplied_role(self):
        response = self.register(role=User.Role.ADMINISTRATOR)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="student@example.edu").exists())

    def test_student_email_requires_exact_ucc_domain_and_normalizes_case(self):
        registration = self.client.post(
            "/api/v1/auth/register/", self.registration_data, format="json"
        )
        self.assertEqual(registration.status_code, status.HTTP_201_CREATED)
        onboarding_token = registration.data["onboarding_token"]

        for invalid_email in (
            "student@gmail.com",
            "student@stu.ucc.edu.gh",
            "student@ucc.edu.gh.example",
        ):
            rejected = self.client.post(
                "/api/v1/auth/role-selection/",
                {
                    "onboarding_token": onboarding_token,
                    "role": User.Role.STUDENT,
                    "student_email": invalid_email,
                },
                format="json",
            )
            self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

        selected = self.client.post(
            "/api/v1/auth/role-selection/",
            {
                "onboarding_token": onboarding_token,
                "role": User.Role.STUDENT,
                "student_email": "Student@UCC.EDU.GH",
            },
            format="json",
        )
        self.assertEqual(selected.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(user.student_email, "student@ucc.edu.gh")
        self.assertEqual(mail.outbox[-1].to, ["student@ucc.edu.gh"])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
    )
    def test_verification_code_is_never_sent_to_the_console_backend(self):
        registration = self.client.post(
            "/api/v1/auth/register/", self.registration_data, format="json"
        )
        response = self.client.post(
            "/api/v1/auth/role-selection/",
            {
                "onboarding_token": registration.data["onboarding_token"],
                "role": User.Role.STUDENT,
                "student_email": "student@ucc.edu.gh",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(
            user.account_status, User.AccountStatus.PENDING_ROLE_SELECTION
        )
        self.assertEqual(user.role, "")
        self.assertFalse(StudentVerification.objects.filter(user=user).exists())
        self.assertEqual(mail.outbox, [])

    def test_verification_code_is_one_time_and_resend_has_cooldown(self):
        self.register()
        user = User.objects.get(email="student@example.edu")
        verification = StudentVerification.objects.get(user=user)
        first_code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

        too_soon = self.client.post(
            "/api/v1/auth/student-email/resend/",
            {"onboarding_token": self.onboarding_token},
            format="json",
        )
        self.assertEqual(too_soon.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(len(mail.outbox), 1)

        verification.last_sent_at = timezone.now() - timedelta(seconds=61)
        verification.save(update_fields=["last_sent_at"])
        resent = self.client.post(
            "/api/v1/auth/student-email/resend/",
            {"onboarding_token": self.onboarding_token},
            format="json",
        )
        self.assertEqual(resent.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

        accepted = self.client.post(
            "/api/v1/auth/student-email/verify/",
            {"onboarding_token": self.onboarding_token, "code": first_code},
            format="json",
        )
        self.assertEqual(accepted.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.student_email_verified)

    def test_facilitator_requires_administrator_approval(self):
        registration = self.client.post(
            "/api/v1/auth/register/", self.registration_data, format="json"
        )
        selected = self.client.post(
            "/api/v1/auth/role-selection/",
            {
                "onboarding_token": registration.data["onboarding_token"],
                "role": User.Role.FACILITATOR,
                "lecturer_profile": {"department": "Computer Science"},
            },
            format="json",
        )
        self.assertEqual(selected.status_code, status.HTTP_200_OK)
        facilitator = User.objects.get(email="student@example.edu")
        self.assertEqual(
            facilitator.account_status, User.AccountStatus.PENDING_APPROVAL
        )
        self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(mail.outbox, [])

        administrator = User.objects.create_superuser(
            email="admin@example.edu",
            password=PASSWORD,
            username="admin",
            first_name="Admin",
            last_name="User",
        )
        self.client.force_authenticate(user=administrator)
        approvals = self.client.get("/api/v1/admin/role-approvals/")
        self.assertEqual(approvals.status_code, status.HTTP_200_OK)
        self.assertEqual(len(approvals.data), 1)
        decision = self.client.post(
            f"/api/v1/admin/role-approvals/{facilitator.pk}/decision/",
            {"status": RoleApproval.Status.APPROVED},
            format="json",
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        facilitator.refresh_from_db()
        self.assertTrue(facilitator.is_active)
        self.assertEqual(
            facilitator.role_approval.status, RoleApproval.Status.APPROVED
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_existing_unverified_student_must_verify_before_login(self):
        user = User.objects.create_user(
            email="legacy@example.edu",
            password=PASSWORD,
            username="legacy",
            first_name="Legacy",
            last_name="Student",
            role=User.Role.STUDENT,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/login/",
                {"email": user.email, "password": PASSWORD},
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}"
        )
        self.assertEqual(
            self.client.get("/api/v1/users/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.credentials()
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/token/refresh/",
                {"refresh": str(RefreshToken.for_user(user))},
                format="json",
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        started = self.client.post(
            "/api/v1/auth/student-email/start/",
            {
                "email": user.email,
                "password": PASSWORD,
                "student_email": "Legacy.Student@UCC.EDU.GH",
            },
            format="json",
        )
        self.assertEqual(started.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(
            user.account_status, User.AccountStatus.PENDING_STUDENT_VERIFICATION
        )
        self.assertEqual(user.student_email, "legacy.student@ucc.edu.gh")
        self.assertEqual(mail.outbox[-1].to, ["legacy.student@ucc.edu.gh"])

        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        confirmed = self.client.post(
            "/api/v1/auth/student-email/verify/",
            {
                "onboarding_token": started.data["onboarding_token"],
                "code": code,
            },
            format="json",
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        self.assertEqual(self.login(email=user.email).status_code, status.HTTP_200_OK)

    @override_settings(
        GOOGLE_CLIENT_ID="google-client-id",
        GOOGLE_CLIENT_SECRET="google-client-secret",
        BACKEND_URL="https://api.example.test",
        FRONTEND_BASE_URL="https://app.example.test/sign-in.html",
    )
    @patch("accounts.oauth._get_json")
    @patch("accounts.oauth.jwt.decode")
    @patch("accounts.oauth.jwt.PyJWKClient")
    @patch("accounts.oauth._post_form")
    def test_google_oauth_uses_one_time_pkce_state_and_creates_pending_user(
        self, post_form, jwk_client, decode, get_json
    ):
        post_form.return_value = {"id_token": "signed-id-token", "access_token": "token"}
        jwk_client.return_value.get_signing_key_from_jwt.return_value.key = "public-key"
        get_json.return_value = {
            "sub": "google-user-123",
            "email": "new.student@example.com",
            "email_verified": True,
            "given_name": "Ama",
            "family_name": "Mensah",
        }

        authorize = self.client.get("/api/v1/auth/oauth/google/")
        self.assertEqual(authorize.status_code, 302)
        query = parse_qs(urlparse(authorize["Location"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn("code_verifier", query)
        state = query["state"][0]
        oauth_state = OAuthState.objects.get()
        decode.return_value = {
            "sub": "google-user-123",
            "nonce": oauth_state.nonce,
            "email": "new.student@example.com",
        }

        callback = self.client.get(
            "/api/v1/auth/oauth/google/callback/",
            {"code": "authorization-code", "state": state},
        )
        self.assertEqual(callback.status_code, 302)
        self.assertIn("onboarding_token", callback["Location"])
        user = User.objects.get(email="new.student@example.com")
        self.assertEqual(
            user.account_status, User.AccountStatus.PENDING_ROLE_SELECTION
        )
        self.assertTrue(
            SocialAccount.objects.filter(
                user=user,
                provider=SocialAccount.Provider.GOOGLE,
                provider_subject="google-user-123",
            ).exists()
        )
        self.assertEqual(post_form.call_args.args[1]["code_verifier"], oauth_state.code_verifier)

        replay = self.client.get(
            "/api/v1/auth/oauth/google/callback/",
            {"code": "authorization-code", "state": state},
        )
        self.assertIn("auth_error=", replay["Location"])

    def test_login_requires_student_email_verification_and_returns_tokens_after(self):
        self.register()
        self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)

        self.activate()
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "student@example.edu")

    def test_refresh_rotates_refresh_token_and_logout_blacklists_it(self):
        self.register()
        user = self.activate()
        login = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        refreshed = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertNotEqual(refreshed.data["refresh"], login.data["refresh"])

        logout = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": refreshed.data["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, status.HTTP_205_RESET_CONTENT)
        invalid_refresh = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": refreshed.data["refresh"]},
            format="json",
        )
        self.assertEqual(invalid_refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_cannot_blacklist_another_users_refresh_token(self):
        self.register()
        self.activate()
        own_login = self.login()
        other_user = User.objects.create_user(
            email="other@example.edu",
            password=PASSWORD,
            first_name="Kojo",
            last_name="Owusu",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        other_login = self.client.post(
            "/api/v1/auth/login/",
            {"email": other_user.email, "password": PASSWORD},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {own_login.data['access']}")

        response = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": other_login.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_profile_update_does_not_change_role_or_email(self):
        self.register()
        self.activate()
        login = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.patch(
            "/api/v1/users/me/",
            {"first_name": "Akua", "role": User.Role.ADMINISTRATOR, "email": "new@example.edu"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Akua")
        self.assertEqual(response.data["role"], User.Role.STUDENT)
        self.assertEqual(response.data["email"], "student@example.edu")

    def test_student_profile_is_owner_scoped_and_student_only(self):
        self.register()
        student = self.activate()
        login = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        updated = self.client.patch(
            "/api/v1/students/me/profile/",
            {"academic_programme": "Computer Science", "location": "Cape Coast"},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["academic_programme"], "Computer Science")

        lecturer = User.objects.create_user(
            email="lecturer@example.edu",
            password=PASSWORD,
            first_name="Kofi",
            last_name="Asare",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=lecturer)
        denied = self.client.get("/api/v1/students/me/profile/")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(student.student_profile.location, "Cape Coast")

    def test_administrator_cannot_activate_unverified_student(self):
        self.register()
        user = User.objects.get(email="student@example.edu")
        administrator = User.objects.create_superuser(
            email="admin@example.edu",
            password=PASSWORD,
            username="admin",
            first_name="Admin",
            last_name="User",
        )

        self.client.force_authenticate(user=administrator)
        activated = self.client.patch(
            f"/api/v1/admin/users/{user.pk}/status/",
            {"account_status": User.AccountStatus.ACTIVE},
            format="json",
        )
        self.assertEqual(activated.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        self.client.force_authenticate(user=None)
        user = self.activate()
        self.assertTrue(user.is_active)

        self.client.force_authenticate(user=user)
        denied = self.client.patch(
            f"/api/v1/admin/users/{administrator.pk}/status/",
            {"account_status": User.AccountStatus.DEACTIVATED},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_account_deactivation_revokes_refresh_tokens(self):
        self.register()
        user = self.activate()
        student_login = self.login()
        administrator = User.objects.create_superuser(
            email="admin@example.edu",
            password=PASSWORD,
            username="admin",
            first_name="Admin",
            last_name="User",
        )
        self.client.force_authenticate(user=administrator)

        deactivated = self.client.patch(
            f"/api/v1/admin/users/{user.pk}/status/",
            {"account_status": User.AccountStatus.DEACTIVATED},
            format="json",
        )
        self.assertEqual(deactivated.status_code, status.HTTP_200_OK)
        refreshed = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": student_login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_django_admin_user_add_form_renders(self):
        administrator = User.objects.create_superuser(
            email="admin@example.edu",
            password=PASSWORD,
            username="admin",
            first_name="Admin",
            last_name="User",
        )
        self.client.force_login(administrator)

        response = self.client.get("/admin/accounts/user/add/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_account_email_is_normalized_and_case_insensitive(self):
        response = self.register(email="STUDENT@EXAMPLE.EDU")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duplicate = self.register(email="Student@example.edu")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_request_and_confirmation_change_password(self):
        self.register()
        self.activate()
        mail.outbox.clear()
        login = self.login()

        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "student@example.edu"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        reset_url = mail.outbox[0].body.splitlines()[-1]
        reset_params = urlparse(reset_url).fragment.partition("?")[2]
        query = parse_qs(reset_params)

        confirmed = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "An0ther$ecure-Password-2026!",
            },
            format="json",
        )

        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="student@example.edu")
        self.assertTrue(user.check_password("An0ther$ecure-Password-2026!"))
        revoked = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(revoked.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_requires_current_password(self):
        self.register()
        self.activate()
        login = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        denied = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "current_password": "incorrect",
                "new_password": "An0ther$ecure-Password-2026!",
            },
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

        changed = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "current_password": PASSWORD,
                "new_password": "An0ther$ecure-Password-2026!",
            },
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(
            User.objects.get(email="student@example.edu").check_password(
                "An0ther$ecure-Password-2026!"
            )
        )

    @patch("accounts.views.create_signed_url", return_value="https://signed.example/photo")
    @patch("accounts.views.upload_private_file", side_effect=lambda *args: args[1])
    def test_profile_photo_upload_validates_image_and_uses_private_storage(
        self, upload_mock, signed_url_mock
    ):
        self.register()
        self.activate()
        login = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        image_buffer = BytesIO()
        Image.new("RGB", (4, 4), color="blue").save(image_buffer, format="PNG")

        response = self.client.post(
            "/api/v1/users/me/profile-photo/",
            {
                "profile_photo": SimpleUploadedFile(
                    "profile.png", image_buffer.getvalue(), content_type="image/png"
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile_photo_url"], "https://signed.example/photo")
        self.assertEqual(upload_mock.call_args.args[0], "profile_photos")
        signed_url_mock.assert_called_once()

