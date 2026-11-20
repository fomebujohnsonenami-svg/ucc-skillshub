from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    related_resource_type = serializers.CharField(
        source="related_content_type.model", read_only=True, allow_null=True
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "related_resource_type",
            "related_object_id",
            "target_url",
            "created_at",
        )
        read_only_fields = fields
