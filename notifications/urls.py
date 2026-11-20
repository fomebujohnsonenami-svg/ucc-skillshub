from django.urls import path

from notifications.views import (
    MarkAllNotificationsReadView,
    NotificationDeleteView,
    NotificationListView,
    NotificationReadView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/mark-all-read/",
        MarkAllNotificationsReadView.as_view(),
        name="notifications-mark-all-read",
    ),
    path(
        "notifications/<int:pk>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
    path(
        "notifications/<int:pk>/",
        NotificationDeleteView.as_view(),
        name="notification-delete",
    ),
]
