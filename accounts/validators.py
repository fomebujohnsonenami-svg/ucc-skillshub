from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

UCC_STUDENT_EMAIL_DOMAIN = "ucc.edu.gh"
email_validator = EmailValidator()


def normalize_ucc_student_email(value):
    email = value.strip().casefold()
    email_validator(email)
    if email.rpartition("@")[2] != UCC_STUDENT_EMAIL_DOMAIN:
        raise ValidationError(
            "Use an official student email ending exactly with @ucc.edu.gh."
        )
    return email


def validate_ucc_student_email(value):
    normalize_ucc_student_email(value)
