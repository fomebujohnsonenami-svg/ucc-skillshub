import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.mail.message import BadHeaderError
from django.db import transaction
from django.utils import timezone

from accounts.models import RoleApproval, StudentProfile, StudentVerification, User

logger = logging.getLogger("accounts")


class VerificationError(Exception):
    pass


class VerificationCooldownError(VerificationError):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__(
            f"Wait {retry_after} seconds before requesting another verification code."
        )


class VerificationEmailError(VerificationError):
    pass


class VerificationRejectedError(VerificationError):
    pass


def _code_hash(user, code, sent_at):
    payload = f"{user.pk}:{sent_at.isoformat()}:{code}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()


def send_student_verification_code(user):
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        raise VerificationEmailError(
            "Console email delivery is disabled for student verification codes."
        )
    now = timezone.now()
    code = f"{secrets.randbelow(1_000_000):06d}"

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        verification = (
            StudentVerification.objects.select_for_update()
            .filter(user=locked_user)
            .first()
        )
        if verification:
            retry_at = verification.last_sent_at + timedelta(
                seconds=settings.STUDENT_VERIFICATION_RESEND_COOLDOWN_SECONDS
            )
            if retry_at > now:
                raise VerificationCooldownError(
                    max(1, int((retry_at - now).total_seconds()))
                )

        if verification is None:
            verification = StudentVerification(
                user=locked_user, student_email=locked_user.student_email
            )
        else:
            verification.student_email = locked_user.student_email
        verification.code_hash = _code_hash(locked_user, code, now)
        verification.expires_at = now + timedelta(
            seconds=settings.STUDENT_VERIFICATION_CODE_TTL_SECONDS
        )
        verification.last_sent_at = now
        verification.failed_attempts = 0
        verification.consumed_at = None
        verification.save()

        try:
            sent_count = send_mail(
                subject="Your UCC SKILLSHUB verification code",
                message=(
                    f"Your UCC SKILLSHUB student email verification code is {code}.\n\n"
                    "This code expires in 10 minutes. If you did not request it, "
                    "you can ignore this message."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[locked_user.student_email],
                fail_silently=False,
            )
            if sent_count != 1:
                raise VerificationEmailError("The verification email was not accepted.")
        except (smtplib.SMTPException, OSError, BadHeaderError) as exc:
            logger.exception(
                "Could not deliver a student verification email to user_id=%s.",
                locked_user.pk,
            )
            raise VerificationEmailError(
                "The verification email could not be sent. Please try again later."
            ) from exc


def confirm_student_verification(user, code):
    now = timezone.now()
    rejection = None

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        verification = (
            StudentVerification.objects.select_for_update()
            .filter(user=locked_user)
            .first()
        )
        if verification is None or verification.consumed_at is not None:
            rejection = "There is no active verification code for this account."
        elif verification.expires_at <= now:
            rejection = "The verification code has expired. Request a new code."
        elif verification.student_email != locked_user.student_email:
            rejection = "The code was sent to a different student email. Request a new code."
        elif verification.failed_attempts >= settings.STUDENT_VERIFICATION_MAX_ATTEMPTS:
            rejection = "Too many incorrect attempts. Request a new code after the cooldown."
        elif not hmac.compare_digest(
            _code_hash(locked_user, code, verification.last_sent_at),
            verification.code_hash,
        ):
            verification.failed_attempts += 1
            verification.save(update_fields=["failed_attempts", "updated_at"])
            rejection = "The verification code is incorrect."
        elif (
            locked_user.account_status
            != User.AccountStatus.PENDING_STUDENT_VERIFICATION
        ):
            rejection = "This student account is not awaiting email verification."
        else:
            verification.consumed_at = now
            verification.save(update_fields=["consumed_at", "updated_at"])
            locked_user.student_email_verified = True
            locked_user.account_status = User.AccountStatus.ACTIVE
            locked_user.save(update_fields=["student_email_verified", "account_status"])
            StudentProfile.objects.get_or_create(user=locked_user)

    if rejection:
        raise VerificationRejectedError(rejection)


def select_role(
    user,
    role,
    student_email="",
    student_profile=None,
    lecturer_profile=None,
    employer_profile=None,
):
    if user.account_status != User.AccountStatus.PENDING_ROLE_SELECTION:
        raise ValueError("This account has already completed role selection.")

    if role == User.Role.STUDENT:
        user.role = role
        user.student_email = student_email
        # Student accounts can sign in immediately after choosing their role.
        # This is not proof of UCC enrollment: keep verification false.
        user.student_email_verified = False
        user.account_status = User.AccountStatus.ACTIVE
        user.save(
            update_fields=[
                "role",
                "student_email",
                "student_email_verified",
                "account_status",
            ]
        )
        StudentProfile.objects.create(user=user, **(student_profile or {}))
    elif role == User.Role.FACILITATOR:
        from accounts.models import LecturerProfile

        user.role = role
        user.account_status = User.AccountStatus.PENDING_APPROVAL
        user.save(update_fields=["role", "account_status"])
        LecturerProfile.objects.create(user=user, **(lecturer_profile or {}))
        RoleApproval.objects.create(user=user)
    elif role == User.Role.RECRUITER:
        from accounts.models import EmployerProfile

        user.role = role
        user.account_status = User.AccountStatus.PENDING_APPROVAL
        user.save(update_fields=["role", "account_status"])
        EmployerProfile.objects.create(user=user, **(employer_profile or {}))
        RoleApproval.objects.create(user=user)
