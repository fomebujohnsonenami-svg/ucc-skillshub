import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("accounts")


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None or response.status_code >= 500:
        logger.error(
            "Unhandled API error",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    return response
