"""Persistent private certificate PDFs stored in Supabase on Vercel."""
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import Storage

from accounts.storage import (
    SupabaseStorageError,
    create_signed_url,
    delete_private_file,
    upload_private_file,
)


class SupabaseCertificateStorage(Storage):
    bucket_kind = "course_resources"

    def _save(self, name, content):
        upload_private_file(
            self.bucket_kind, name, content.read(), "application/pdf"
        )
        return name

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Certificate storage is read-only.")
        bucket = quote(settings.SUPABASE_BUCKETS[self.bucket_kind], safe="")
        path = quote(name, safe="/")
        url = f"{settings.SUPABASE_URL}/storage/v1/object/authenticated/{bucket}/{path}"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                data = response.read()
        except (HTTPError, URLError) as exc:
            raise SupabaseStorageError("Certificate PDF could not be downloaded.") from exc
        return File(BytesIO(data), name=name)

    def exists(self, name):
        bucket = quote(settings.SUPABASE_BUCKETS[self.bucket_kind], safe="")
        path = quote(name, safe="/")
        url = f"{settings.SUPABASE_URL}/storage/v1/object/authenticated/{bucket}/{path}"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }
        try:
            with urlopen(Request(url, headers=headers, method="HEAD"), timeout=10):
                return True
        except HTTPError as exc:
            if exc.code == 404:
                return False
            raise SupabaseStorageError("Unable to check certificate storage.") from exc
        except URLError as exc:
            raise SupabaseStorageError("Unable to reach certificate storage.") from exc

    def url(self, name):
        return create_signed_url(self.bucket_kind, name)

    def delete(self, name):
        if name:
            delete_private_file(self.bucket_kind, name)
