import secrets
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


def new_certificate_id():
    return f"UCCS-{uuid.uuid4().hex[:20].upper()}"


def new_verification_token():
    return secrets.token_urlsafe(32)


class Certificate(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="certificates",
    )
    pathway = models.ForeignKey(
        "pathways.SkillPathway",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="certificates",
    )
    certificate_id = models.CharField(
        max_length=32, unique=True, default=new_certificate_id, editable=False
    )
    issuing_organization = models.CharField(max_length=200, default="UCC SKILLSHUB")
    issue_date = models.DateField(auto_now_add=True)
    completion_info = models.JSONField(default=dict, blank=True)
    verification_token = models.CharField(
        max_length=64, unique=True, default=new_verification_token, editable=False
    )
    certificate_file = models.FileField(
        upload_to="certificates/%Y/%m/", blank=True, max_length=512
    )
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-issue_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(course__isnull=False, pathway__isnull=True)
                    | Q(course__isnull=True, pathway__isnull=False)
                ),
                name="certificates_exactly_one_learning_item",
            ),
            models.UniqueConstraint(
                fields=("student", "course"),
                condition=Q(course__isnull=False),
                name="certificates_student_course_unique",
            ),
            models.UniqueConstraint(
                fields=("student", "pathway"),
                condition=Q(pathway__isnull=False),
                name="certificates_student_pathway_unique",
            ),
        ]

    @property
    def learning_item_name(self):
        return self.course.title if self.course_id else self.pathway.name

    def __str__(self):
        return f"{self.certificate_id}: {self.learning_item_name}"


class Achievement(models.Model):
    class Category(models.TextChoices):
        COURSE = "course", "Course"
        PATHWAY = "pathway", "Pathway"
        STREAK = "streak", "Learning streak"
        PROJECT = "project", "Project"
        COMMUNITY = "community", "Community"

    key = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField()
    badge_image = models.CharField(max_length=512, blank=True)
    award_criteria = models.JSONField(default=dict)
    category = models.CharField(max_length=20, choices=Category.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("category", "name")

    def __str__(self):
        return self.name


class StudentAchievement(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="earned_achievements",
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.CASCADE, related_name="awards"
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-awarded_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "achievement"),
                name="certificates_student_achievement_unique",
            )
        ]

    def __str__(self):
        return f"{self.achievement} awarded to {self.student_id}"
