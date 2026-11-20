"""Serve existing frontend HTML without altering its contents or template syntax."""
import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_safe

from config.frontend_static import PAGE_FOLDERS, ROOT, frontend_asset


@require_safe
def frontend(request, resource=""):
    if resource in ("", "/"):
        resource = "skillbridge_public_landing_page/code.html"

    # Only expose explicitly known frontend pages.
    if resource.endswith("/code.html") and resource.split("/")[0] in PAGE_FOLDERS:
        if resource != resource.split("/")[0] + "/code.html":
            raise Http404("Page not found.")
        path = (ROOT / resource).resolve()
        if not path.is_file() or not path.is_relative_to(ROOT):
            raise Http404("Page not found.")
        return HttpResponse(path.read_bytes(), content_type="text/html; charset=utf-8")

    # Vercel may not expose all application asset files at the CDN URL.
    # Serve only allowlisted static assets directly from the deployed function.
    asset_path = frontend_asset(resource)
    if asset_path:
        content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        response = FileResponse(asset_path.open("rb"), content_type=content_type)
        response["Cache-Control"] = "public, max-age=86400"
        return response
    raise Http404("Page not found.")
