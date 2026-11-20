from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        COURSE_ANNOUNCEMENT = "course_announcement", "Course announcement"
        ENROLLMENT_CONFIRMATION = "enrollment_confirmation", "Enrollment confirmation"
        LEARNING_PROGRESS = "learning_progress", "Learning progress"
        PROJECT_SUBMISSION = "project_submission", "Project submission"
        LECTURER_FEEDBACK = "lecturer_feedback", "Lecturer feedback"
        CERTIFICATE_ISSUED = "certificate_issued", "Certificate issued"
        NEW_OPPORTUNITY = "new_opportunity", "New opportunity"
        APPLICATION_STATUS = "application_status", "Application status"
        PATHWAY_MILESTONE = "pathway_milestone", "Pathway milestone"
        PLATFORM_ANNOUNCEMENT = "platform_announcement", "Platform announcement"
        ACHIEVEMENT_AWARDED = "achievement_awarded", "Achievement awarded"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=2000)
    notification_type = models.CharField(max_length=32, choices=Type.choices)
    is_read = models.BooleanField(default=False, db_index=True)
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    related_object_id = models.CharField(max_length=100, blank=True)
    related_resource = GenericForeignKey(
        "related_content_type", "related_object_id"
    )
    target_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("recipient", "is_read", "-created_at"),
                name="notif_recipient_read_created",
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.recipient_id})"
