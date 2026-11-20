import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils.text import slugify


class StudentPortfolio(models.Model):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolio",
    )
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    headline = models.CharField(max_length=200, blank=True)
    biography = models.TextField(blank=True, max_length=4000)
    academic_programme = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=150, blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    is_public = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__username",)

    def save(self, *args, **kwargs):
        if not self.slug:
            name = self.student.get_full_name() or self.student.username
            base_slug = slugify(name)[:70] or "portfolio"
            self.slug = f"{base_slug}-{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Portfolio for {self.student_id}"


class PortfolioSkill(models.Model):
    class Proficiency(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"
        EXPERT = "expert", "Expert"

    portfolio = models.ForeignKey(
        StudentPortfolio, on_delete=models.CASCADE, related_name="skills"
    )
    name = models.CharField(max_length=100)
    proficiency = models.CharField(
        max_length=20, choices=Proficiency.choices, default=Proficiency.INTERMEDIATE
    )
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "portfolio",
                name="portfolios_skill_name_per_portfolio_ci_unique",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.portfolio_id})"


class PortfolioProject(models.Model):
    portfolio = models.ForeignKey(
        StudentPortfolio, on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=5000)
    role = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=100, blank=True)
    skills = models.JSONField(default=list, blank=True)
    repository_url = models.URLField(blank=True)
    demo_url = models.URLField(blank=True)
    image_url = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_featured", "display_order", "-created_at", "-id")

    def __str__(self):
        return self.title


class PortfolioCertificate(models.Model):
    portfolio = models.ForeignKey(
        StudentPortfolio, on_delete=models.CASCADE, related_name="certificates"
    )
    certificate = models.ForeignKey(
        "certificates.Certificate",
        on_delete=models.CASCADE,
        related_name="portfolio_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-certificate__issue_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "certificate"),
                name="portfolios_certificate_link_unique",
            )
        ]

    def __str__(self):
        return f"{self.certificate_id} in portfolio {self.portfolio_id}"


class PortfolioSocialLink(models.Model):
    class Platform(models.TextChoices):
        WEBSITE = "website", "Website"
        OTHER = "other", "Other"

    portfolio = models.ForeignKey(
        StudentPortfolio, on_delete=models.CASCADE, related_name="social_links"
    )
    platform = models.CharField(
        max_length=20, choices=Platform.choices, default=Platform.OTHER
    )
    label = models.CharField(max_length=100)
    url = models.URLField(max_length=500)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_order", "label", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "url"),
                name="portfolios_social_url_per_portfolio_unique",
            )
        ]

    def __str__(self):
        return f"{self.label} ({self.portfolio_id})"
