import logging
import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.models import (
    EmailChangeVerification,
    EmployerProfile,
    LecturerProfile,
    RoleApproval,
    SocialAccount,
    StudentProfile,
    User,
    UserSettings,
)
from accounts.email_changes import (
    EmailChangeCooldown,
    EmailChangeEmailError,
    EmailChangeRejected,
    confirm_email_change,
    start_email_change,
)
from accounts.onboarding import create_onboarding_token, get_onboarding_user
from accounts.permissions import IsAdministrator, IsStudent
from accounts.serializers import (
    AccountSettingsSerializer,
    AccountStatusSerializer,
    ChangePasswordSerializer,
    EmailChangeConfirmSerializer,
    EmailChangeStartSerializer,
    LoginSerializer,
    LogoutSerializer,
    MessageSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfilePhotoResponseSerializer,
    ProfilePhotoUploadSerializer,
    RegistrationSerializer,
    RegistrationResponseSerializer,
    RoleApprovalDecisionSerializer,
    RoleApprovalSerializer,
    RoleSelectionSerializer,
    RoleSelectionResponseSerializer,
    StudentProfileSerializer,
    StudentVerificationConfirmSerializer,
    StudentVerificationConfirmResponseSerializer,
    StudentVerificationRequestSerializer,
    StudentVerificationStartResponseSerializer,
    StudentVerificationStartSerializer,
    SecureTokenRefreshSerializer,
    UserSerializer,
    build_password_reset_token,
)
from accounts.storage import (
    SupabaseStorageError,
    create_signed_url,
    delete_private_file,
    upload_private_file,
)
from accounts.token_utils import revoke_refresh_tokens
from accounts.verification import (
    VerificationCooldownError,
    VerificationEmailError,
    VerificationRejectedError,
    confirm_student_verification,
    select_role,
    send_student_verification_code,
)

logger = logging.getLogger("accounts")


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegistrationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    @extend_schema(responses={201: RegistrationResponseSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Registration received. Choose your account role to continue.",
                "onboarding_token": create_onboarding_token(user),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RoleSelectionView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_role_selection"

    @extend_schema(
        request=RoleSelectionSerializer,
        responses={200: RoleSelectionResponseSerializer},
    )
    def post(self, request):
        serializer = RoleSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = get_onboarding_user(
                    serializer.validated_data["onboarding_token"],
                    [User.AccountStatus.PENDING_ROLE_SELECTION],
                )
                user = User.objects.select_for_update().get(pk=user.pk)
                data = serializer.validated_data
                select_role(
                    user,
                    data["role"],
                    student_email=data.get("student_email", ""),
                    student_profile=data.get("student_profile"),
                    lecturer_profile=data.get("lecturer_profile"),
                    employer_profile=data.get("employer_profile"),
                )
         except ValueError as exc:
            raise serializers.ValidationError(
                {"onboarding_token": str(exc)}
            ) from exc
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"student_email": "This student email is already registered."}
            ) from exc
        except VerificationCooldownError as exc:
            return Response(
                {"detail": str(exc), "retry_after": exc.retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(exc.retry_after)},
            )
        except VerificationEmailError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if user.role == User.Role.STUDENT:
            # Return tokens so the registration flow can enter the dashboard
            # without requesting an email verification code.
            refresh = RefreshToken.for_user(user)
            response_data = {
                "message": "Your student account is ready.",
                "status": user.account_status,
                "onboarding_token": None,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        else:
            response_data = {
                "message": (
                    "Your request is pending administrator approval. "
                    "You can sign in after approval."
                ),
                "status": user.account_status,
                "onboarding_token": None,
            }
        return Response(response_data, status=status.HTTP_200_OK)


class StudentVerificationResendView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_verification_request"

    @extend_schema(
        request=StudentVerificationRequestSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request):
        serializer = StudentVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = get_onboarding_user(
                serializer.validated_data["onboarding_token"],
                [User.AccountStatus.PENDING_STUDENT_VERIFICATION],
            )
            send_student_verification_code(user)
        except ValueError as exc:
            raise serializers.ValidationError(
                {"onboarding_token": str(exc)}
            ) from exc
        except VerificationCooldownError as exc:
            return Response(
                {"detail": str(exc), "retry_after": exc.retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(exc.retry_after)},
            )
        except VerificationEmailError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {"message": "A new verification code was sent to your UCC student email."},
            status=status.HTTP_200_OK,
        )


class StudentVerificationStartView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_verification_start"

    @extend_schema(
        request=StudentVerificationStartSerializer,
        responses={200: StudentVerificationStartResponseSerializer},
    )
    def post(self, request):
        serializer = StudentVerificationStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.filter(
            email__iexact=data["email"],
            role=User.Role.STUDENT,
            account_status__in=(
                User.AccountStatus.ACTIVE,
                User.AccountStatus.PENDING,
            ),
            student_email_verified=False,
        ).first()
        if user is None or not user.check_password(data["password"]):
            raise serializers.ValidationError(
                {"detail": "The account could not be verified for this request."}
            )
        if User.objects.filter(student_email__iexact=data["student_email"]).exclude(
            pk=user.pk
        ).exists():
            raise serializers.ValidationError(
                {"student_email": "This student email is already registered."}
            )

        user.student_email = data["student_email"]
        user.save(update_fields=["student_email"])
        try:
            send_student_verification_code(user)
        except VerificationCooldownError as exc:
            return Response(
                {"detail": str(exc), "retry_after": exc.retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(exc.retry_after)},
            )
        except VerificationEmailError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        user.account_status = User.AccountStatus.PENDING_STUDENT_VERIFICATION
        user.save(update_fields=["account_status"])
        return Response(
            {
                "message": "A verification code was sent to your UCC student email.",
                "onboarding_token": create_onboarding_token(user),
            },
            status=status.HTTP_200_OK,
        )


class StudentVerificationConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "student_verification_confirm"

    @extend_schema(
        request=StudentVerificationConfirmSerializer,
        responses={200: StudentVerificationConfirmResponseSerializer},
    )
    def post(self, request):
        serializer = StudentVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = get_onboarding_user(
                serializer.validated_data["onboarding_token"],
                [User.AccountStatus.PENDING_STUDENT_VERIFICATION],
            )
            confirm_student_verification(user, serializer.validated_data["code"])
            user.refresh_from_db()
        except ValueError as exc:
            raise serializers.ValidationError(
                {"onboarding_token": str(exc)}
            ) from exc
        except VerificationRejectedError as exc:
            raise serializers.ValidationError({"code": str(exc)}) from exc
        response_data = {
            "message": "Your UCC student email is verified. You can now sign in.",
            "user": UserSerializer(user).data,
        }
        if SocialAccount.objects.filter(user=user).exists():
            refresh = RefreshToken.for_user(user)
            response_data["access"] = str(refresh.access_token)
            response_data["refresh"] = str(refresh)
        return Response(response_data, status=status.HTTP_200_OK)


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={205: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            if str(refresh.payload.get("user_id")) != str(request.user.pk):
                return Response(
                    {"detail": "The refresh token does not belong to this account."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            refresh.blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "The refresh token is invalid or expired."}
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class RefreshTokenView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SecureTokenRefreshSerializer


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            account_status=User.AccountStatus.ACTIVE,
        ).first()
        if user:
            token_data = build_password_reset_token(user)
            reset_url = settings.FRONTEND_BASE_URL or request.build_absolute_uri("/")
            reset_url = f"{reset_url}#password-reset?{urlencode(token_data)}"
            send_mail(
                subject="Reset your UCC SKILLSHUB password",
                message=(
                    "Use the following link to reset your UCC SKILLSHUB password. "
                    "If you did not request this, you can ignore this message.\n\n"
                    f"{reset_url}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        return Response(
            {
                "message": (
                    "If an active account exists for that email, password reset "
                    "instructions will be sent."
                )
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        revoke_refresh_tokens(user)
        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        revoke_refresh_tokens(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class AccountSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _profile(user):
        if user.role == User.Role.STUDENT:
            return StudentProfile.objects.filter(user=user).first()
        if user.role == User.Role.LECTURER:
            return LecturerProfile.objects.filter(user=user).first()
        if user.role in {User.Role.EMPLOYER, User.Role.RECRUITER}:
            return EmployerProfile.objects.filter(user=user).first()
        return None

    def _response_data(self, user):
        user_settings, _ = UserSettings.objects.get_or_create(user=user)
        profile = self._profile(user)
        pending_email = EmailChangeVerification.objects.filter(
            user=user, expires_at__gt=timezone.now()
        ).values_list("new_email", flat=True).first()
        is_student = user.role == User.Role.STUDENT
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "pending_email": pending_email,
            "role": user.role,
            "phone_number": getattr(profile, "phone_number", ""),
            "academic_programme": (
                getattr(profile, "academic_programme", "") if is_student else ""
            ),
            "academic_level": (
                getattr(profile, "academic_level", "") if is_student else ""
            ),
            "biography": getattr(profile, "biography", ""),
            "profile_visibility": (
                getattr(profile, "profile_visibility", StudentProfile.Visibility.PRIVATE)
                if is_student
                else None
            ),
            "profile_photo_url": UserSerializer(user).data["profile_photo_url"],
            "theme": user_settings.theme,
            "notification_preferences": user_settings.notification_preferences,
        }

    def get(self, request):
        return Response(self._response_data(request.user))

    def patch(self, request):
        serializer = AccountSettingsSerializer(
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data
        user = request.user

        with transaction.atomic():
            user_fields = ("first_name", "last_name", "username")
            changed_user_fields = []
            for field in user_fields:
                if field in changes:
                    setattr(user, field, changes[field])
                    changed_user_fields.append(field)
            if changed_user_fields:
                user.save(update_fields=changed_user_fields)

            profile_fields = {
                field: changes[field]
                for field in (
                    "phone_number",
                    "academic_programme",
                    "academic_level",
                    "biography",
                    "profile_visibility",
                )
                if field in changes
            }
            if profile_fields:
                profile = self._profile(user)
                if profile is None and user.role == User.Role.STUDENT:
                    profile = StudentProfile.objects.create(user=user)
                elif profile is None and user.role == User.Role.LECTURER:
                    profile = LecturerProfile.objects.create(user=user)
                if profile is None:
                    raise serializers.ValidationError(
                        {
                            "phone_number": (
                                "A profile must be configured before these details "
                                "can be changed."
                            )
                        }
                    )
                for field, value in profile_fields.items():
                    if not hasattr(profile, field):
                        raise serializers.ValidationError(
                            {field: "This setting is not available to this account."}
                        )
                    setattr(profile, field, value)
                profile.save(update_fields=tuple(profile_fields))

            settings_fields = ("theme", "notification_preferences")
            settings_changes = {
                field: changes[field]
                for field in settings_fields
                if field in changes
            }
            if settings_changes:
                user_settings, _ = UserSettings.objects.get_or_create(user=user)
                if "notification_preferences" in settings_changes:
                    preferences = dict(user_settings.notification_preferences)
                    preferences.update(settings_changes["notification_preferences"])
                    settings_changes["notification_preferences"] = preferences
                for field, value in settings_changes.items():
                    setattr(user_settings, field, value)
                user_settings.save(update_fields=(*settings_changes, "updated_at"))

        return Response(self._response_data(user))


class EmailChangeStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_change_request"

    @extend_schema(request=EmailChangeStartSerializer, responses={202: MessageSerializer})
    def post(self, request):
        serializer = EmailChangeStartSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            verification = start_email_change(
                request.user, serializer.validated_data["new_email"]
            )
        except EmailChangeCooldown as exc:
            return Response(
                {"detail": "Please wait before requesting another verification code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(exc.retry_after)},
            )
        except EmailChangeRejected as exc:
            raise serializers.ValidationError({"new_email": str(exc)}) from exc
        except EmailChangeEmailError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(
            {
                "message": "A verification code was sent to the new email address.",
                "pending_email": verification.new_email,
                "expires_at": verification.expires_at,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class EmailChangeConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_change_confirm"

    @extend_schema(request=EmailChangeConfirmSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = EmailChangeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            confirm_email_change(request.user, serializer.validated_data["code"])
        except EmailChangeRejected as exc:
            raise serializers.ValidationError({"code": str(exc)}) from exc
        request.user.refresh_from_db()
        return Response(UserSerializer(request.user).data)


class StudentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        profile, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        return profile


class ProfilePhotoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    max_file_size = 5 * 1024 * 1024
    allowed_formats = {
        "JPEG": ("jpg", "image/jpeg"),
        "PNG": ("png", "image/png"),
        "WEBP": ("webp", "image/webp"),
    }

    @extend_schema(
        request=ProfilePhotoUploadSerializer,
        responses={200: ProfilePhotoResponseSerializer},
    )
    def post(self, request):
        photo = request.FILES.get("profile_photo")
        if not photo:
            raise serializers.ValidationError(
                {"profile_photo": "A profile photo file is required."}
            )
        if photo.size > self.max_file_size:
            raise serializers.ValidationError(
                {"profile_photo": "The image must be 5 MB or smaller."}
            )

        try:
            image = Image.open(photo)
            image_format = image.format
            width, height = image.size
            image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise serializers.ValidationError(
                {"profile_photo": "Upload a valid JPEG, PNG, or WebP image."}
            ) from exc
        if image_format not in self.allowed_formats or width * height > 20_000_000:
            raise serializers.ValidationError(
                {"profile_photo": "Upload a valid JPEG, PNG, or WebP image."}
            )
        extension, content_type = self.allowed_formats[image_format]
        if photo.content_type and photo.content_type != content_type:
            raise serializers.ValidationError(
                {"profile_photo": "The file content does not match its image type."}
            )
        photo.seek(0)
        object_path = f"{request.user.pk}/{uuid.uuid4().hex}.{extension}"
        old_path = request.user.profile_photo_path
        stored_path = upload_private_file(
            "profile_photos", object_path, photo.read(), content_type
        )
        request.user.profile_photo_path = stored_path
        request.user.save(update_fields=["profile_photo_path"])
        if old_path:
            try:
                delete_private_file("profile_photos", old_path)
            except SupabaseStorageError:
                logger.exception("Could not remove a replaced private profile photo.")
        return Response(
            {"profile_photo_url": create_signed_url("profile_photos", stored_path)},
            status=status.HTTP_200_OK,
        )


class AdministratorAccountStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    @extend_schema(
        request=AccountStatusSerializer,
        responses={200: UserSerializer},
    )
    def patch(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        serializer = AccountStatusSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        requested_status = serializer.validated_data["account_status"]
        if requested_status == User.AccountStatus.ACTIVE:
            if not user.role:
                return Response(
                    {"detail": "Complete role selection before activating this account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user.role in {User.Role.FACILITATOR, User.Role.RECRUITER} and not (
                RoleApproval.objects.filter(
                    user=user, status=RoleApproval.Status.APPROVED
                ).exists()
            ):
                return Response(
                    {"detail": "This role must be approved through the approval workflow."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if user.pk == request.user.pk and serializer.validated_data[
            "account_status"
        ] != User.AccountStatus.ACTIVE:
            return Response(
                {"detail": "Administrators cannot deactivate their own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        if not user.is_active:
            revoke_refresh_tokens(user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AdministratorRoleApprovalListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    @extend_schema(responses={200: RoleApprovalSerializer(many=True)})
    def get(self, request):
        approvals = RoleApproval.objects.filter(
            status=RoleApproval.Status.PENDING
        ).select_related("user").order_by("submitted_at")
        return Response(RoleApprovalSerializer(approvals, many=True).data)


class AdministratorRoleApprovalDecisionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]

    @extend_schema(
        request=RoleApprovalDecisionSerializer,
        responses={200: RoleApprovalSerializer},
    )
    def post(self, request, user_id):
        serializer = RoleApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            approval = get_object_or_404(
                RoleApproval.objects.select_for_update().select_related("user"),
                user_id=user_id,
            )
            if approval.status != RoleApproval.Status.PENDING:
                raise serializers.ValidationError(
                    {"status": "This role request has already been decided."}
                )
            if approval.user.role not in {
                User.Role.FACILITATOR,
                User.Role.RECRUITER,
            }:
                raise serializers.ValidationError(
                    {"status": "This account is not awaiting a supported role approval."}
                )
            decision = serializer.validated_data["status"]
            approval.status = decision
            approval.decision_note = serializer.validated_data.get(
                "decision_note", ""
            )
            approval.decided_by = request.user
            approval.decided_at = timezone.now()
            approval.save(
                update_fields=[
                    "status",
                    "decision_note",
                    "decided_by",
                    "decided_at",
                ]
            )
            approval.user.account_status = (
                User.AccountStatus.ACTIVE
                if decision == RoleApproval.Status.APPROVED
                else User.AccountStatus.DEACTIVATED
            )
            approval.user.save(update_fields=["account_status"])
        return Response(RoleApprovalSerializer(approval).data)


