import base64
import hashlib
import json
import logging
import secrets
from datetime import timedelta
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import jwt
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.auth_rules import user_authentication_rule
from accounts.models import OAuthState, SocialAccount, User
from accounts.onboarding import create_onboarding_token

logger = logging.getLogger("accounts")
OAUTH_STATE_SALT = "accounts.oauth.state.v1"


class OAuthError(Exception):
    pass


PROVIDERS = {
    SocialAccount.Provider.GOOGLE: {
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
        "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
        "jwks_endpoint": "https://www.googleapis.com/oauth2/v3/certs",
        "issuer": ["https://accounts.google.com", "accounts.google.com"],
        "scope": "openid email profile",
    },
    SocialAccount.Provider.LINKEDIN: {
        "authorization_endpoint": "https://www.linkedin.com/oauth/v2/authorization",
        "token_endpoint": "https://www.linkedin.com/oauth/v2/accessToken",
        "userinfo_endpoint": "https://api.linkedin.com/v2/userinfo",
        "jwks_endpoint": "https://www.linkedin.com/oauth/openid/jwks",
        "issuer": "https://www.linkedin.com",
        "scope": "openid profile email",
    },
}


def _client_credentials(provider):
    if provider == SocialAccount.Provider.GOOGLE:
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
    elif provider == SocialAccount.Provider.LINKEDIN:
        client_id = settings.LINKEDIN_CLIENT_ID
        client_secret = settings.LINKEDIN_CLIENT_SECRET
    else:
        raise OAuthError("Unsupported identity provider.")
    if not client_id or not client_secret:
        raise OAuthError("This identity provider is not configured.")
    if not settings.BACKEND_URL or not settings.FRONTEND_BASE_URL:
        raise OAuthError("The OAuth callback URLs are not configured.")
    return client_id, client_secret


def _callback_uri(provider):
    return (
        f"{settings.BACKEND_URL}"
        f"{reverse('oauth-callback', kwargs={'provider': provider})}"
    )


def create_authorization_url(provider):
    client_id, _ = _client_credentials(provider)
    provider_config = PROVIDERS[provider]
    state = signing.dumps(
        {"provider": provider, "state_id": secrets.token_urlsafe(32)},
        salt=OAUTH_STATE_SALT,
    )
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    now = timezone.now()

    with transaction.atomic():
        OAuthState.objects.filter(expires_at__lte=now).delete()
        OAuthState.objects.create(
            provider=provider,
            state_hash=hashlib.sha256(state.encode("ascii")).hexdigest(),
            nonce=nonce,
            code_verifier=code_verifier,
            expires_at=now + timedelta(seconds=settings.OAUTH_STATE_MAX_AGE),
        )

    query = {
        "client_id": client_id,
        "redirect_uri": _callback_uri(provider),
        "response_type": "code",
        "scope": provider_config["scope"],
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{provider_config['authorization_endpoint']}?{urlencode(query)}"


def _post_form(url, values):
    request = Request(
        url,
        data=urlencode(values).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise OAuthError("The identity provider returned an invalid response.")
    return payload


def _get_json(url, access_token):
    request = Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise OAuthError("The identity provider returned an invalid response.")
    return payload


def _exchange_and_validate(provider, code, state):
    client_id, client_secret = _client_credentials(provider)
    config = PROVIDERS[provider]
    try:
        state_payload = signing.loads(
            state,
            salt=OAUTH_STATE_SALT,
            max_age=settings.OAUTH_STATE_MAX_AGE,
        )
    except BadSignature as exc:
        raise OAuthError("The sign-in request is invalid or has expired.") from exc
    if state_payload.get("provider") != provider:
        raise OAuthError("The sign-in request is invalid or has expired.")
    now = timezone.now()
    state_hash = hashlib.sha256(state.encode("ascii")).hexdigest()

    with transaction.atomic():
        oauth_state = (
            OAuthState.objects.select_for_update()
            .filter(
                provider=provider,
                state_hash=state_hash,
                consumed_at__isnull=True,
                expires_at__gt=now,
            )
            .first()
        )
        if oauth_state is None:
            raise OAuthError("The sign-in request is invalid or has expired.")
        oauth_state.consumed_at = now
        oauth_state.save(update_fields=["consumed_at"])
        nonce = oauth_state.nonce
        code_verifier = oauth_state.code_verifier

    tokens = _post_form(
        config["token_endpoint"],
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _callback_uri(provider),
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": code_verifier,
        },
    )
    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")
    if not id_token or not access_token:
        raise OAuthError("The identity provider did not return required credentials.")

    jwks_client = jwt.PyJWKClient(config["jwks_endpoint"], timeout=5)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=config["issuer"],
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
    )
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OAuthError("The identity provider response could not be verified.")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise OAuthError("The identity provider response could not be verified.")

    userinfo = _get_json(config["userinfo_endpoint"], access_token)
    if userinfo.get("sub") != subject:
        raise OAuthError("The identity provider response could not be verified.")
    email = userinfo.get("email", "")
    if (
        not isinstance(email, str)
        or not email
        or userinfo.get("email_verified") is not True
    ):
        raise OAuthError("The identity provider email is not verified.")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise OAuthError("The identity provider email is invalid.") from exc
    claim_email = claims.get("email")
    if claim_email is not None and (
        not isinstance(claim_email, str)
        or claim_email.casefold() != email.casefold()
    ):
        raise OAuthError("The identity provider response could not be verified.")

    return claims, userinfo, email.casefold()


def authenticate_oauth_identity(provider, code, state):
    claims, userinfo, email = _exchange_and_validate(provider, code, state)
    subject = claims["sub"]

    try:
        with transaction.atomic():
            social_account = (
                SocialAccount.objects.select_related("user")
                .filter(provider=provider, provider_subject=subject)
                .first()
            )
            if social_account:
                user = social_account.user
            else:
                if User.objects.filter(email__iexact=email).exists():
                    raise OAuthError(
                        "An account already uses this email. Sign in with email first."
                    )
                user = User.objects.create_user(
                    email=email,
                    password=None,
                    first_name=str(userinfo.get("given_name", ""))[:150],
                    last_name=str(userinfo.get("family_name", ""))[:150],
                    role="",
                    account_status=User.AccountStatus.PENDING_ROLE_SELECTION,
                    email_verified=True,
                )
                SocialAccount.objects.create(
                    user=user,
                    provider=provider,
                    provider_subject=subject,
                )
    except IntegrityError as exc:
        logger.info("OAuth identity registration encountered a uniqueness conflict.")
        raise OAuthError(
            "An account could not be created for this provider identity."
        ) from exc

    if user.account_status in {
        User.AccountStatus.PENDING_ROLE_SELECTION,
        User.AccountStatus.PENDING_STUDENT_VERIFICATION,
    }:
        return {
            "onboarding_token": create_onboarding_token(user),
            "status": user.account_status,
        }
    if user.account_status == User.AccountStatus.PENDING_APPROVAL:
        return {"status": user.account_status}
    if not user_authentication_rule(user):
        raise OAuthError("This account is not permitted to sign in.")

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "status": user.account_status,
    }
