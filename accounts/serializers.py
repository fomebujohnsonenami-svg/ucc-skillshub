from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import (
    EmployerProfile,
    LecturerProfile,
    RoleApproval,
    StudentProfile,
    User,
)
from accounts.storage import create_signed_url
from accounts.validators import normalize_ucc_student_email


class StudentProfileInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = (
            "student_id",
            "academic_programme",
            "department",
            "faculty",
            "academic_level",
            "phone_number",
            "location",
            "biography",
            "profile_visibility",
        )
        extra_kwargs = {"student_id": {"required": False, "allow_null": True}}


class UserSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "account_status",
            "email_verified",
            "student_email",
            "student_email_verified",
            "profile_photo_url",
            "date_joined",
            "last_login",
        )
        read_only_fields = (
            "id",
            "email",
            "role",
            "account_status",
            "email_verified",
            "student_email",
            "student_email_verified",
            "profile_photo_url",
            "date_joined",
            "last_login",
        )

    def get_profile_photo_url(self, user) -> str | None:
        if not user.profile_photo_path:
            return None
        return create_signed_url("profile_photos", user.profile_photo_path)


class RegistrationResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    onboarding_token = serializers.CharField()
    user = UserSerializer()


class RoleSelectionResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    status = serializers.CharField()
    onboarding_token = serializers.CharField(allow_null=True)


class StudentVerificationStartResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    onboarding_token = serializers.CharField()


class StudentVerificationConfirmResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    user = UserSerializer()
    access = serializers.CharField(required=False)
    refresh = serializers.CharField(required=False)


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "password",
        )
        extra_kwargs = {"username": {"required": False}}

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate_email(self, value):
        email = User.objects.normalize_email(value).casefold()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate(self, attrs):
        if "role" in self.initial_data:
            raise serializers.ValidationError(
                {"role": "Choose your role after registration."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            **validated_data,
            role="",
            account_status=User.AccountStatus.PENDING_ROLE_SELECTION,
        )
        return user


class LecturerProfileInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = LecturerProfile
        fields = ("department", "faculty", "biography", "phone_number")


class EmployerProfileInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = ("organization_name", "job_title", "website", "phone_number")


class RoleSelectionSerializer(serializers.Serializer):
    onboarding_token = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=(User.Role.STUDENT, User.Role.FACILITATOR, User.Role.RECRUITER)
    )
    student_email = serializers.EmailField(required=False)
    student_profile = StudentProfileInputSerializer(required=False)
    lecturer_profile = LecturerProfileInputSerializer(required=False)
    employer_profile = EmployerProfileInputSerializer(required=False)

    def validate_student_email(self, value):
        try:
            return normalize_ucc_student_email(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate(self, attrs):
        role = attrs["role"]
        if role == User.Role.STUDENT:
            if not attrs.get("student_email"):
                raise serializers.ValidationError(
                    {"student_email": "An official @ucc.edu.gh student email is required."}
                )
            if User.objects.filter(
                student_email__iexact=attrs["student_email"]
            ).exists():
                raise serializers.ValidationError(
                    {"student_email": "This student email is already registered."}
                )
        elif role == User.Role.RECRUITER:
            organization = attrs.get("employer_profile", {})
            if not organization.get("organization_name", "").strip():
                raise serializers.ValidationError(
                    {
                        "employer_profile": {
                            "organization_name": "An organization name is required."
                        }
                    }
                )
        return attrs


class StudentVerificationRequestSerializer(serializers.Serializer):
    onboarding_token = serializers.CharField(write_only=True)


class StudentVerificationStartSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    student_email = serializers.EmailField()

    def validate_email(self, value):
        return User.objects.normalize_email(value).casefold()

    def validate_student_email(self, value):
        try:
            return normalize_ucc_student_email(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class StudentVerificationConfirmSerializer(StudentVerificationRequestSerializer):
    code = serializers.RegexField(r"^\d{6}$", write_only=True)


class RoleApprovalSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = RoleApproval
        fields = (
            "id",
            "user_email",
            "first_name",
            "last_name",
            "role",
            "organization_name",
            "status",
            "submitted_at",
            "decided_at",
            "decision_note",
        )
        read_only_fields = fields

    def get_organization_name(self, approval) -> str:
        profile = getattr(approval.user, "employer_profile", None)
        return profile.organization_name if profile else ""


class RoleApprovalDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(RoleApproval.Status.APPROVED, RoleApproval.Status.REJECTED)
    )
    decision_note = serializers.CharField(required=False, allow_blank=True)


class LoginSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return User.objects.normalize_email(value).casefold()

    def validate(self, attrs):
        tokens = super().validate(attrs)
        tokens["user"] = UserSerializer(self.user).data
        return tokens


class SecureTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        with transaction.atomic():
            token = RefreshToken(attrs["refresh"])
            user_id = token.get(api_settings.USER_ID_CLAIM)
            user = User.objects.select_for_update().filter(
                **{api_settings.USER_ID_FIELD: user_id}
            ).first()
            if not user or not api_settings.USER_AUTHENTICATION_RULE(user):
                raise AuthenticationFailed(
                    "No active account found with the given credentials."
                )
            return super().validate(attrs)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate(self, attrs):
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, account_status=User.AccountStatus.ACTIVE)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})
        password_validation.validate_password(attrs["new_password"], user)
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = (
            "student_id",
            "academic_programme",
            "department",
            "faculty",
            "academic_level",
            "phone_number",
            "location",
            "biography",
            "profile_visibility",
        )


class AccountStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("account_status",)

    def validate_account_status(self, value):
        if value not in {
            User.AccountStatus.ACTIVE,
            User.AccountStatus.SUSPENDED,
            User.AccountStatus.DEACTIVATED,
        }:
            raise serializers.ValidationError("Unsupported account status.")
        return value

    def validate(self, attrs):
        if "account_status" not in attrs:
            raise serializers.ValidationError(
                {"account_status": "An account status is required."}
            )
        return attrs


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class ProfilePhotoUploadSerializer(serializers.Serializer):
    profile_photo = serializers.ImageField()


class ProfilePhotoResponseSerializer(serializers.Serializer):
    profile_photo_url = serializers.URLField()


def build_password_reset_token(user):
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }
