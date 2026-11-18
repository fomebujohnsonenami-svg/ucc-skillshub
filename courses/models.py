import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class CourseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "course categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Course(models.Model):
    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"
        ALL_LEVELS = "all", "All levels"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    thumbnail_path = models.CharField(max_length=512, blank=True)
    category = models.ForeignKey(
        CourseCategory, on_delete=models.PROTECT, related_name="courses"
    )
    instructors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="CourseInstructor",
        related_name="instructed_courses",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_courses",
    )
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER
    )
    estimated_duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    learning_objectives = models.JSONField(default=list, blank=True)
    prerequisites = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    certificate_eligible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "category")),
            models.Index(fields=("status", "difficulty")),
            models.Index(fields=("status", "estimated_duration_minutes")),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or uuid.uuid4().hex
            slug = base_slug
            suffix = 2
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CourseInstructor(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="course_instructors"
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="course_instructor_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("course", "instructor"),
                name="courses_course_instructor_unique",
            )
        ]
        ordering = ("assigned_at",)

    def __str__(self):
        return f"{self.instructor} — {self.course}"


class CourseModule(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("course", "order"), name="courses_module_order_unique"
            )
        ]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class Lesson(models.Model):
    class ContentType(models.TextChoices):
        TEXT = "text", "Text"
        VIDEO = "video", "Video"
        RESOURCE = "resource", "Downloadable resources"

    module = models.ForeignKey(
        CourseModule, on_delete=models.CASCADE, related_name="lessons"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content_type = models.CharField(
        max_length=20, choices=ContentType.choices, default=ContentType.TEXT
    )
    content = models.TextField(blank=True)
    video_url = models.URLField(
        blank=True, validators=[URLValidator(schemes=["https"])]
    )
    duration_minutes = models.PositiveSmallIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)
    is_preview = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("module", "order"), name="courses_lesson_order_unique"
            )
        ]

    @property
    def course(self):
        return self.module.course

    def __str__(self):
        return f"{self.module.title}: {self.title}"


class CourseEnrollment(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="enrollments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )
    last_accessed_lesson = models.ForeignKey(
        Lesson,
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
                fields=("course", "student"), name="courses_enrollment_unique"
            )
        ]
        indexes = [models.Index(fields=("student", "status"))]

    def __str__(self):
        return f"{self.student} — {self.course}"


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(
        CourseEnrollment, on_delete=models.CASCADE, related_name="lesson_progress"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="student_progress"
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("lesson__module__order", "lesson__order")
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "lesson"), name="courses_lesson_progress_unique"
            ),
            models.CheckConstraint(
                condition=Q(is_completed=True, completed_at__isnull=False)
                | Q(is_completed=False, completed_at__isnull=True),
                name="courses_lesson_progress_completion_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.enrollment.student} — {self.lesson}"


class CourseReview(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="reviews"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("course", "student"), name="courses_review_unique"
            )
        ]

    def __str__(self):
        return f"{self.course.title}: {self.rating}/5 by {self.student}"


class CourseResource(models.Model):
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="resources"
    )
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True)
    object_path = models.CharField(max_length=512, unique=True)
    content_type = models.CharField(max_length=150)
    file_size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_course_resources",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return self.title
