import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import EmailChangeVerification, User
from accounts.token_utils import revoke_refresh_tokens

logger = logging.getLogger("accounts")

EMAIL_CHANGE_CODE_TTL_SECONDS = 600
EMAIL_CHANGE_RESEND_COOLDOWN_SECONDS = 60
EMAIL_CHANGE_MAX_ATTEMPTS = 5


class EmailChangeRejected(Exception):
    pass


class EmailChangeCooldown(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after


class EmailChangeEmailError(Exception):
    pass


def start_email_change(user, new_email):
    new_email = User.objects.normalize_email(new_email).casefold()
    if new_email == user.email:
        raise EmailChangeRejected("The new email is already in use by this account.")
    if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        raise EmailChangeRejected("A user with this email already exists.")

    now = timezone.now()
    verification = EmailChangeVerification.objects.filter(user=user).first()
    if verification:
        retry_after = int(
            (
                verification.last_sent_at
                + timedelta(seconds=EMAIL_CHANGE_RESEND_COOLDOWN_SECONDS)
                - now
            ).total_seconds()
        )
        if retry_after > 0:
            raise EmailChangeCooldown(retry_after)

    code = f"{secrets.randbelow(1_000_000):06d}"
    defaults = {
        "new_email": new_email,
        "code_hash": make_password(code),
        "expires_at": now + timedelta(seconds=EMAIL_CHANGE_CODE_TTL_SECONDS),
        "last_sent_at": now,
        "failed_attempts": 0,
    }
    try:
        verification, _ = EmailChangeVerification.objects.update_or_create(
            user=user, defaults=defaults
        )
    except IntegrityError as exc:
        raise EmailChangeRejected(
            "This email address already has a pending verification."
        ) from exc
    try:
        delivered = send_mail(
            subject="Verify your UCC SKILLSHUB email change",
            message=(
                f"Your verification code is {code}. "
                "It expires in 10 minutes. If you did not request this change, "
                "you can ignore this message."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[new_email],
            fail_silently=False,
        )
        if not delivered:
            raise EmailChangeEmailError("The verification email was not delivered.")
    except (SMTPException, OSError, ValueError) as exc:
        verification.delete()
        logger.exception("Could not send an account email-change verification.")
        raise EmailChangeEmailError(
            "The verification email could not be sent."
        ) from exc
    except EmailChangeEmailError:
        verification.delete()
        raise

    return verification


def confirm_email_change(user, code):
    invalid_code = False
    with transaction.atomic():
        verification = (
            EmailChangeVerification.objects.select_for_update()
            .filter(user=user)
            .first()
        )
        if (
            verification is None
            or verification.expires_at <= timezone.now()
            or verification.failed_attempts >= EMAIL_CHANGE_MAX_ATTEMPTS
        ):
            raise EmailChangeRejected("The verification code is invalid or expired.")

        if not check_password(code, verification.code_hash):
            verification.failed_attempts += 1
            verification.save(update_fields=("failed_attempts", "updated_at"))
            invalid_code = True
        else:
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            if (
                User.objects.filter(email__iexact=verification.new_email)
                .exclude(pk=locked_user.pk)
                .exists()
            ):
                raise EmailChangeRejected("A user with this email already exists.")
            locked_user.email = verification.new_email
            locked_user.email_verified = True
            locked_user.save(update_fields=("email", "email_verified"))
            verification.delete()
            revoke_refresh_tokens(locked_user)

    if invalid_code:
        raise EmailChangeRejected("The verification code is incorrect.")
