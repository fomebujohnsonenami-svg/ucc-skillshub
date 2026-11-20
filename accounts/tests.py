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
    EmailChangeVerification,
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
        student_email = registration_overrides.pop("student_email", None)
        response = self.client.post(
            "/api/v1/auth/register/",
            {**self.registration_data, **registration_overrides},
            format="json",
        )
        if response.status_code == status.HTTP_201_CREATED:
            payload = {
                "onboarding_token": response.data["onboarding_token"],
                "role": User.Role.STUDENT,
            }
            if student_email is not None:
                payload["student_email"] = student_email
            selected = self.client.post(
                "/api/v1/auth/role-selection/", payload, format="json"
            )
            self.assertEqual(selected.status_code, status.HTTP_200_OK)
            self.assertEqual(selected.data["status"], User.AccountStatus.ACTIVE)
            self.assertIn("access", selected.data)
            self.assertIn("refresh", selected.data)
        return response

    def activate(self, email="student@example.edu"):
        user = User.objects.get(email=email)
        self.assertTrue(user.is_active)
        return user

    def login(self, email="student@example.edu"):
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": PASSWORD},
            format="json",
        )

    def test_registration_activates_student_without_email_code(self):
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.is_active)
        self.assertEqual(user.student_email, "")
        self.assertFalse(user.student_email_verified)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_registration_rejects_client_supplied_role(self):
        response = self.register(role=User.Role.ADMINISTRATOR)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="student@example.edu").exists())

    def test_optional_student_email_must_have_ucc_domain(self):
        registration = self.client.post(
            "/api/v1/auth/register/", self.registration_data, format="json"
        )
        onboarding_token = registration.data["onboarding_token"]
        rejected = self.client.post(
            "/api/v1/auth/role-selection/",
            {
                "onboarding_token": onboarding_token,
                "role": User.Role.STUDENT,
                "student_email": "student@gmail.com",
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
                "student_profile": {"academic_programme": "Computer Science"},
            },
            format="json",
        )
        self.assertEqual(selected.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(user.student_email, "student@ucc.edu.gh")
        self.assertFalse(user.student_email_verified)
        self.assertEqual(user.student_profile.academic_programme, "Computer Science")
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_students_can_register_when_email_delivery_is_unavailable(self):
        self.register()
        self.assertTrue(User.objects.get(email="student@example.edu").is_active)

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

    def test_active_student_without_verified_email_can_authenticate(self):
        user = User.objects.create_user(
            email="legacy@example.edu",
            password=PASSWORD,
            username="legacy",
            first_name="Legacy",
            last_name="Student",
            role=User.Role.STUDENT,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.assertFalse(user.student_email_verified)
        response = self.login(email=user.email)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )
        self.assertEqual(
            self.client.get("/api/v1/students/me/profile/").status_code,
            status.HTTP_200_OK,
        )

    def test_student_role_selection_returns_tokens_for_immediate_login(self):
        registration = self.client.post(
            "/api/v1/auth/register/", self.registration_data, format="json"
        )
        selected = self.client.post(
            "/api/v1/auth/role-selection/",
            {
                "onboarding_token": registration.data["onboarding_token"],
                "role": User.Role.STUDENT,
                "student_profile": {"academic_programme": "Computer Science"},
            },
            format="json",
        )
        self.assertEqual(selected.status_code, status.HTTP_200_OK)
        self.assertEqual(selected.data["status"], User.AccountStatus.ACTIVE)
        self.assertIsNone(selected.data["onboarding_token"])
        self.assertIn("access", selected.data)
        self.assertIn("refresh", selected.data)
        self.assertEqual(selected.data["user"]["role"], User.Role.STUDENT)
        user = User.objects.get(email="student@example.edu")
        self.assertEqual(user.student_profile.academic_programme, "Computer Science")
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

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

    def test_administrator_can_manage_active_student_account(self):
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
        suspended = self.client.patch(
            f"/api/v1/admin/users/{user.pk}/status/",
            {"account_status": User.AccountStatus.SUSPENDED},
            format="json",
        )
        self.assertEqual(suspended.status_code, status.HTTP_200_OK)
        restored = self.client.patch(
            f"/api/v1/admin/users/{user.pk}/status/",
            {"account_status": User.AccountStatus.ACTIVE},
            format="json",
        )
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(user.student_email_verified)

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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountSettingsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="settings@example.edu",
            password=PASSWORD,
            username="settings-user",
            first_name="Ama",
            last_name="Mensah",
            student_email="settings@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

    def test_settings_update_persists_preferences_and_keeps_privileged_fields_read_only(self):
        response = self.client.patch(
            "/api/v1/settings/",
            {
                "first_name": "Akua",
                "username": "akua-mensah",
                "phone_number": "+233200000000",
                "academic_programme": "Computer Science",
                "academic_level": "300",
                "biography": "Learning software engineering.",
                "profile_visibility": "public",
                "theme": "dark",
                "notification_preferences": {
                    "new_opportunity": False,
                    "certificate_issued": True,
                },
                "role": User.Role.ADMINISTRATOR,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ama")
        self.assertEqual(self.user.role, User.Role.STUDENT)

        response = self.client.patch(
            "/api/v1/settings/",
            {
                "first_name": "Akua",
                "username": "akua-mensah",
                "phone_number": "+233200000000",
                "academic_programme": "Computer Science",
                "academic_level": "300",
                "biography": "Learning software engineering.",
                "profile_visibility": "public",
                "theme": "dark",
                "notification_preferences": {
                    "new_opportunity": False,
                    "certificate_issued": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Akua")
        self.assertEqual(self.user.email, "settings@example.edu")
        self.assertEqual(self.user.role, User.Role.STUDENT)
        self.assertEqual(response.data["academic_programme"], "Computer Science")
        self.assertEqual(response.data["theme"], "dark")
        self.assertFalse(response.data["notification_preferences"]["new_opportunity"])
        self.assertTrue(
            response.data["notification_preferences"]["certificate_issued"]
        )

    def test_email_changes_only_after_one_time_code_is_confirmed(self):
        start = self.client.post(
            "/api/v1/settings/email-change/",
            {
                "current_password": PASSWORD,
                "new_email": "New.Address@example.edu",
            },
            format="json",
        )

        self.assertEqual(start.status_code, status.HTTP_202_ACCEPTED, start.data)
        self.assertEqual(start.data["pending_email"], "new.address@example.edu")
        verification = EmailChangeVerification.objects.get(user=self.user)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        self.assertNotEqual(code, verification.code_hash)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "settings@example.edu")

        confirmed = self.client.post(
            "/api/v1/settings/email-change/confirm/",
            {"code": code},
            format="json",
        )

        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new.address@example.edu")
        self.assertTrue(self.user.email_verified)
        self.assertFalse(
            EmailChangeVerification.objects.filter(user=self.user).exists()
        )

    def test_settings_reject_email_and_student_only_fields_for_other_roles(self):
        email_change = self.client.patch(
            "/api/v1/settings/",
            {"email": "unsafe@example.edu"},
            format="json",
        )
        self.assertEqual(email_change.status_code, status.HTTP_400_BAD_REQUEST)

        lecturer = User.objects.create_user(
            email="lecturer-settings@example.edu",
            password=PASSWORD,
            username="lecturer-settings",
            first_name="Kofi",
            last_name="Asare",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=lecturer)
        denied = self.client.patch(
            "/api/v1/settings/",
            {"academic_programme": "Computer Science"},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

