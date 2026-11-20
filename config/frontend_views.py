"""Serve existing frontend HTML without altering its contents or template syntax."""
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
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

    # Original UI uses relative asset URLs. Redirect them to the collected CDN
    # assets while preserving every link and script tag in the HTML itself.
    if frontend_asset(resource):
        return HttpResponseRedirect(f"{settings.STATIC_URL}{resource}")
    raise Http404("Page not found.")
