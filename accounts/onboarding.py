from django.core import signing

from accounts.models import User

ONBOARDING_TOKEN_SALT = "accounts.onboarding.v1"
ONBOARDING_TOKEN_MAX_AGE = 30 * 60


def create_onboarding_token(user):
    return signing.dumps({"user_id": str(user.pk)}, salt=ONBOARDING_TOKEN_SALT)


def get_onboarding_user(token, statuses):
    try:
        payload = signing.loads(
            token,
            salt=ONBOARDING_TOKEN_SALT,
            max_age=ONBOARDING_TOKEN_MAX_AGE,
        )
    except signing.BadSignature as exc:
        raise ValueError("The onboarding link is invalid or expired.") from exc

    user = User.objects.filter(
        pk=payload.get("user_id"),
        account_status__in=statuses,
    ).first()
    if user is None:
        raise ValueError("This onboarding step is unavailable or already completed.")
    return user
