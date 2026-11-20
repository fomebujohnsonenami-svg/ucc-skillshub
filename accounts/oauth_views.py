import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode

import jwt
from django.conf import settings
from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import SocialAccount
from accounts.oauth import (
    OAuthError,
    authenticate_oauth_identity,
    create_authorization_url,
)

logger = logging.getLogger("accounts")


class OAuthProvidersSerializer(serializers.Serializer):
    google = serializers.BooleanField()


def _frontend_redirect(payload):
    if not settings.FRONTEND_BASE_URL:
        return Response(
            {"detail": "OAuth frontend redirect URL is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return HttpResponseRedirect(
        f"{settings.FRONTEND_BASE_URL}#oauth?{urlencode(payload)}"
    )


class OAuthAuthorizeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth_authorize"

    @extend_schema(
        responses={
            302: OpenApiResponse(description="Redirect to the identity provider."),
            503: OpenApiResponse(description="Provider credentials are not configured."),
        }
    )
    def get(self, request, provider):
        if provider not in SocialAccount.Provider.values:
            return Response(
                {"detail": "Unsupported identity provider."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            return HttpResponseRedirect(create_authorization_url(provider))
        except OAuthError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class OAuthProvidersView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: OAuthProvidersSerializer})
    def get(self, request):
        configured = bool(settings.BACKEND_URL and settings.FRONTEND_BASE_URL)
        return Response(
            {
                SocialAccount.Provider.GOOGLE: bool(
                    configured
                    and settings.GOOGLE_CLIENT_ID
                    and settings.GOOGLE_CLIENT_SECRET
                )
            }
        )


class OAuthCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth_callback"

    @extend_schema(
        responses={
            302: OpenApiResponse(description="Return to the sign-in page."),
            503: OpenApiResponse(description="The frontend redirect URL is not configured."),
        }
    )
    def get(self, request, provider):
        if provider not in SocialAccount.Provider.values:
            return Response(
                {"detail": "Unsupported identity provider."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if request.query_params.get("error"):
            return _frontend_redirect({"auth_error": "provider_denied"})

        code = request.query_params.get("code", "")
        oauth_state = request.query_params.get("state", "")
        if not code or not oauth_state:
            return _frontend_redirect({"auth_error": "invalid_response"})

        try:
            result = authenticate_oauth_identity(provider, code, oauth_state)
        except (
            OAuthError,
            jwt.PyJWTError,
            URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ):
            logger.warning("OAuth authentication failed for provider=%s.", provider)
            return _frontend_redirect({"auth_error": "provider_authentication_failed"})

        if "access" in result:
            payload = {
                "access": result["access"],
                "refresh": result["refresh"],
                "status": result["status"],
            }
        elif "onboarding_token" in result:
            payload = {
                "onboarding_token": result["onboarding_token"],
                "status": result["status"],
            }
        else:
            payload = {"status": result["status"]}
        return _frontend_redirect(payload)
