import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from courses.models import Course


class SkillCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "skill categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Skill(models.Model):
    category = models.ForeignKey(
        SkillCategory, on_delete=models.PROTECT, related_name="skills"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("category", "name"), name="pathways_skill_category_name_uniq"
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SkillPathway(models.Model):
    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"
        ALL_LEVELS = "all", "All levels"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    category = models.ForeignKey(
        SkillCategory, on_delete=models.PROTECT, related_name="pathways"
    )
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER
    )
    estimated_duration_weeks = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    thumbnail_path = models.CharField(max_length=512, blank=True)
    required_skills = models.ManyToManyField(
        Skill, blank=True, related_name="required_by_pathways"
    )
    recommended_courses = models.ManyToManyField(
        Course, blank=True, related_name="recommended_by_pathways"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_pathways",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=("status", "category", "difficulty"))]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or uuid.uuid4().hex
            slug = base_slug
            suffix = 2
            while SkillPathway.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PathwayStep(models.Model):
    pathway = models.ForeignKey(
        SkillPathway, on_delete=models.CASCADE, related_name="steps"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    estimated_duration_weeks = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    recommended_course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pathway_steps",
    )
    project_title = models.CharField(max_length=200, blank=True)
    project_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("pathway", "order"))]

    def __str__(self):
        return f"{self.pathway.name}: {self.title}"


class StudentPathwayEnrollment(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    pathway = models.ForeignKey(
        SkillPathway, on_delete=models.CASCADE, related_name="enrollments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pathway_enrollments",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )
    last_accessed_step = models.ForeignKey(
        PathwayStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="last_accessed_enrollments",
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-last_accessed_at", "-enrolled_at")
        constraints = [
            models.UniqueConstraint(
                fields=("pathway", "student"), name="pathway_student_enrollment_uniq"
            )
        ]
        indexes = [models.Index(fields=("student", "status"))]

    def __str__(self):
        return f"{self.student} — {self.pathway}"


class PathwayStepProgress(models.Model):
    enrollment = models.ForeignKey(
        StudentPathwayEnrollment, on_delete=models.CASCADE, related_name="step_progress"
    )
    step = models.ForeignKey(
        PathwayStep, on_delete=models.CASCADE, related_name="student_progress"
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("step__order", "step_id")
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "step"), name="pathway_step_enrollment_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(is_completed=True, completed_at__isnull=False)
                | models.Q(is_completed=False, completed_at__isnull=True),
                name="pathway_step_completion_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.enrollment.student} — {self.step}"
