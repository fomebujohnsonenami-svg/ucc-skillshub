import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils.text import slugify

from accounts.notification_preferences import default_notification_preferences
from accounts.validators import validate_ucc_student_email


class UserManager(BaseUserManager):
    use_in_migrations = True

    @transaction.atomic
    def create_user(self, email, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).casefold()
        if not username:
            base = slugify(email.partition("@")[0]) or "user"
            username = base
            suffix = 1
            while self.model.objects.filter(username=username).exists():
                username = f"{base}{suffix}"
                suffix += 1
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, username=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMINISTRATOR)
        extra_fields.setdefault("account_status", User.AccountStatus.ACTIVE)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have staff and superuser permissions.")
        return self.create_user(email, password, username, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        LECTURER = "lecturer", "Lecturer"
        FACILITATOR = "facilitator", "Facilitator"
        ADMINISTRATOR = "administrator", "Administrator"
        EMPLOYER = "employer", "Employer"
        RECRUITER = "recruiter", "Recruiter"

    class AccountStatus(models.TextChoices):
        PENDING = "pending", "Pending administrator approval"
        PENDING_ROLE_SELECTION = "pending_role_selection", "Pending role selection"
        PENDING_STUDENT_VERIFICATION = (
            "pending_student_verification",
            "Pending student email verification",
        )
        PENDING_APPROVAL = "pending_approval", "Pending administrator approval"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        blank=True,
        db_index=True,
    )
    account_status = models.CharField(
        max_length=32,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING,
        db_index=True,
    )
    email_verified = models.BooleanField(default=False)
    student_email = models.EmailField(
        blank=True, default="", validators=[validate_ucc_student_email]
    )
    student_email_verified = models.BooleanField(default=False)
    profile_photo_path = models.CharField(max_length=512, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_staff = models.BooleanField(default=False)
    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_uniq"),
            models.UniqueConstraint(
                Lower("student_email"),
                condition=~models.Q(student_email=""),
                name="accounts_user_student_email_ci_uniq",
            ),
        ]

    @property
    def is_active(self):
        return self.account_status == self.AccountStatus.ACTIVE

    def clean(self):
        super().clean()
        if (
            self.role == self.Role.STUDENT
            and self.account_status == self.AccountStatus.ACTIVE
            and not self.student_email_verified
        ):
            raise ValidationError(
                {"account_status": "Verify the UCC student email before activation."}
            )
        if (
            self.role in {self.Role.FACILITATOR, self.Role.RECRUITER}
            and self.account_status == self.AccountStatus.ACTIVE
            and self.pk
            and not RoleApproval.objects.filter(
                user_id=self.pk, status=RoleApproval.Status.APPROVED
            ).exists()
        ):
            raise ValidationError(
                {"account_status": "Approve the role request before activation."}
            )

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalize_email(self.email).casefold()
        if self.student_email:
            self.student_email = self.student_email.strip().casefold()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return self.email


class StudentProfile(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        UNIVERSITY = "university", "University members"
        PUBLIC = "public", "Public"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    student_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    academic_programme = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    faculty = models.CharField(max_length=200, blank=True)
    academic_level = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    location = models.CharField(max_length=200, blank=True)
    biography = models.TextField(blank=True)
    profile_visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )

    def __str__(self):
        return f"Student profile: {self.user.email}"


class UserSettings(models.Model):
    class Theme(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"
        SYSTEM = "system", "System default"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="settings"
    )
    theme = models.CharField(
        max_length=10, choices=Theme.choices, default=Theme.SYSTEM
    )
    notification_preferences = models.JSONField(
        default=default_notification_preferences, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.user_id}"


class EmailChangeVerification(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="email_change_verification"
    )
    new_email = models.EmailField()
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("new_email"), name="accounts_pending_email_ci_unique"
            )
        ]

    def __str__(self):
        return f"Email change verification for {self.user_id}"


class LecturerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="lecturer_profile"
    )
    department = models.CharField(max_length=200, blank=True)
    faculty = models.CharField(max_length=200, blank=True)
    biography = models.TextField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"Lecturer profile: {self.user.email}"


class EmployerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="employer_profile"
    )
    organization_name = models.CharField(max_length=200)
    job_title = models.CharField(max_length=150, blank=True)
    website = models.URLField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"{self.organization_name} ({self.user.email})"


class StudentVerification(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_verification"
    )
    student_email = models.EmailField(validators=[validate_ucc_student_email])
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Student email verification for {self.user_id}"


class SocialAccount(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="social_accounts"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    provider_subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "provider_subject"),
                name="accounts_social_provider_subject_uniq",
            ),
            models.UniqueConstraint(
                fields=("provider", "user"),
                name="accounts_social_provider_user_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.provider} account for {self.user_id}"


class OAuthState(models.Model):
    provider = models.CharField(max_length=16, choices=SocialAccount.Provider.choices)
    state_hash = models.CharField(max_length=64, unique=True)
    nonce = models.CharField(max_length=128)
    code_verifier = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} OAuth state {self.pk}"


class RoleApproval(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="role_approval"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_approval_decisions",
    )
    decision_note = models.TextField(blank=True)

    def __str__(self):
        return f"Role approval for {self.user_id}: {self.status}"
