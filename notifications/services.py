from django.contrib.contenttypes.models import ContentType

from accounts.models import User, UserSettings
from notifications.models import Notification


def create_notification(
    recipient,
    *,
    title,
    message,
    notification_type,
    related_resource=None,
    target_url="",
):
    preferences = UserSettings.objects.filter(user=recipient).values_list(
        "notification_preferences", flat=True
    ).first()
    if preferences and preferences.get(notification_type) is False:
        return None

    values = {
        "recipient": recipient,
        "title": title,
        "message": message,
        "notification_type": notification_type,
        "target_url": target_url,
    }
    if related_resource is not None:
        values["related_content_type"] = ContentType.objects.get_for_model(
            related_resource, for_concrete_model=False
        )
        values["related_object_id"] = str(related_resource.pk)
    return Notification.objects.create(**values)


def create_notifications(recipients, **notification):
    recipients = list(recipients)
    if not recipients:
        return []
    preferences = {
        item.user_id: item.notification_preferences
        for item in UserSettings.objects.filter(
            user_id__in=[recipient.pk for recipient in recipients]
        ).only("user_id", "notification_preferences")
    }
    values = {
        key: notification[key]
        for key in ("title", "message", "notification_type", "target_url")
        if key in notification
    }
    related_resource = notification.get("related_resource")
    if related_resource is not None:
        values["related_content_type"] = ContentType.objects.get_for_model(
            related_resource, for_concrete_model=False
        )
        values["related_object_id"] = str(related_resource.pk)
    pending = [
        Notification(recipient=recipient, **values)
        for recipient in recipients
        if preferences.get(recipient.pk, {}).get(notification["notification_type"])
        is not False
    ]
    return Notification.objects.bulk_create(pending)


def notify_students(**notification):
    students = User.objects.filter(
        role=User.Role.STUDENT,
        account_status=User.AccountStatus.ACTIVE,
        student_email_verified=True,
    )
    return create_notifications(students, **notification)
