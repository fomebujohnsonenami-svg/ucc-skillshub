from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify


class OpportunityCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "opportunity categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OpportunitySkill(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="opportunities_skill_name_ci_unique"
            )
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Opportunity(models.Model):
    class WorkArrangement(models.TextChoices):
        REMOTE = "remote", "Remote"
        HYBRID = "hybrid", "Hybrid"
        ONSITE = "onsite", "On-site"

    class PublicationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    category = models.ForeignKey(
        OpportunityCategory, on_delete=models.PROTECT, related_name="opportunities"
    )
    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200)
    description = models.TextField()
    responsibilities = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    required_skills = models.ManyToManyField(
        OpportunitySkill, blank=True, related_name="opportunities"
    )
    location = models.CharField(max_length=200, blank=True)
    work_arrangement = models.CharField(
        max_length=16,
        choices=WorkArrangement.choices,
        default=WorkArrangement.ONSITE,
    )
    opportunity_type = models.CharField(max_length=60, blank=True)
    compensation = models.CharField(max_length=120, blank=True)
    application_deadline = models.DateTimeField()
    application_instructions = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_opportunities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("application_deadline", "-created_at")
        indexes = [
            models.Index(fields=("status", "application_deadline")),
            models.Index(fields=("category", "status")),
            models.Index(fields=("work_arrangement", "status")),
        ]

    def clean(self):
        super().clean()
        errors = {}
        now = timezone.now()
        if self.application_deadline and self.closes_at:
            if self.closes_at < self.application_deadline:
                errors["closes_at"] = (
                    "The closing date must be on or after the application deadline."
                )
        if self.status == self.PublicationStatus.PUBLISHED:
            if not self.application_deadline or self.application_deadline <= now:
                errors["application_deadline"] = (
                    "A published opportunity must have a future deadline."
                )
            if self.closes_at and self.closes_at <= now:
                errors["closes_at"] = (
                    "A published opportunity must not be past its closing date."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == self.PublicationStatus.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        now = timezone.now()
        return (
            self.status == self.PublicationStatus.PUBLISHED
            and self.application_deadline > now
            and (self.closes_at is None or self.closes_at > now)
        )

    def __str__(self):
        return f"{self.title} — {self.organization}"


class OpportunityApplication(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        UNDER_REVIEW = "under_review", "Under Review"
        SHORTLISTED = "shortlisted", "Shortlisted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.PROTECT, related_name="applications"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="opportunity_applications",
    )
    portfolio = models.ForeignKey(
        "portfolios.StudentPortfolio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunity_applications",
    )
    statement = models.TextField(
        validators=[MinLengthValidator(1)], max_length=5000
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPLIED,
        db_index=True,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_opportunity_applications",
    )
    review_note = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ("-submitted_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("opportunity", "student"),
                name="opportunities_application_once_per_student",
            )
        ]
        indexes = [models.Index(fields=("student", "status"))]

    def __str__(self):
        return f"{self.student_id} applied to {self.opportunity_id}"


class ApplicationAttachment(models.Model):
    application = models.ForeignKey(
        OpportunityApplication, on_delete=models.CASCADE, related_name="attachments"
    )
    file_name = models.CharField(max_length=255)
    object_path = models.CharField(max_length=512, unique=True)
    content_type = models.CharField(max_length=150)
    file_size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_application_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at", "id")

    def __str__(self):
        return self.file_name
