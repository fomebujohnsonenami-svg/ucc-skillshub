import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("accounts")


class SupabaseStorageError(Exception):
    pass


def _require_credentials():
    if (
        not settings.SUPABASE_URL.startswith("https://")
        or not settings.SUPABASE_SERVICE_ROLE_KEY
    ):
        raise ImproperlyConfigured(
            "An HTTPS SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for private storage."
        )


def _object_path(object_path):
    if (
        not object_path
        or object_path.startswith("/")
        or "\\" in object_path
        or any(part in {"", ".", ".."} for part in object_path.split("/"))
    ):
        raise ValueError("A valid relative storage object path is required.")
    return quote(object_path, safe="/")


def _request(method, endpoint, *, body=None, content_type="application/json"):
    _require_credentials()
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": content_type,
    }
    request = Request(
        f"{settings.SUPABASE_URL}/storage/v1/{endpoint}",
        data=payload,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read()
    except HTTPError as exc:
        logger.error("Supabase Storage returned HTTP %s.", exc.code)
        raise SupabaseStorageError(
            f"Supabase Storage returned HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        logger.error("Supabase Storage request failed: %s", exc.reason)
        raise SupabaseStorageError("Supabase Storage could not be reached.") from exc

    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise SupabaseStorageError(
            "Supabase Storage returned an invalid response."
        ) from exc


def _bucket(bucket_kind):
    try:
        bucket = settings.SUPABASE_BUCKETS[bucket_kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported private storage bucket: {bucket_kind}.") from exc
    if not bucket:
        raise ImproperlyConfigured(f"The Supabase bucket for {bucket_kind} is empty.")
    return bucket


def upload_private_file(bucket_kind, object_path, content, content_type):
    bucket = quote(_bucket(bucket_kind), safe="")
    path = _object_path(object_path)
    endpoint = f"object/{bucket}/{path}"
    _require_credentials()
    request = Request(
        f"{settings.SUPABASE_URL}/storage/v1/{endpoint}",
        data=content,
        headers={
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "false",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as exc:
        logger.error("Supabase Storage upload returned HTTP %s.", exc.code)
        raise SupabaseStorageError(
            f"Supabase Storage upload returned HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        logger.error("Supabase Storage upload failed: %s", exc.reason)
        raise SupabaseStorageError("Supabase Storage could not be reached.") from exc
    return object_path


def create_signed_url(bucket_kind, object_path, expires_in=None):
    bucket = quote(_bucket(bucket_kind), safe="")
    path = _object_path(object_path)
    lifetime = (
        settings.SUPABASE_SIGNED_URL_TTL if expires_in is None else expires_in
    )
    if not 1 <= lifetime <= 3600:
        raise ValueError("Signed URL lifetime must be between 1 and 3600 seconds.")
    response = _request(
        "POST",
        f"object/sign/{bucket}/{path}",
        body={"expiresIn": lifetime},
    )
    signed_path = response.get("signedURL") or response.get("signedUrl")
    if not signed_path:
        raise SupabaseStorageError("Supabase Storage did not return a signed URL.")
    if signed_path.startswith("http://") or signed_path.startswith("https://"):
        return signed_path
    prefix = "" if signed_path.startswith("/storage/v1/") else "/storage/v1"
    return f"{settings.SUPABASE_URL}{prefix}{signed_path}"


def delete_private_file(bucket_kind, object_path):
    bucket = quote(_bucket(bucket_kind), safe="")
    _object_path(object_path)
    _request(
        "DELETE",
        f"object/{bucket}",
        body={"prefixes": [object_path]},
    )
