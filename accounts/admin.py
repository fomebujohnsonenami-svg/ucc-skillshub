from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from accounts.models import EmployerProfile, LecturerProfile, StudentProfile, User
from accounts.token_utils import revoke_refresh_tokens


class SkillsHubUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "account_status",
        )


class SkillsHubUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = SkillsHubUserChangeForm
    add_form = SkillsHubUserCreationForm
    ordering = ("email",)
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "role",
        "account_status",
        "student_email_verified",
        "is_staff",
    )
    list_filter = ("role", "account_status", "student_email_verified", "is_staff")
    search_fields = (
        "email",
        "student_email",
        "username",
        "first_name",
        "last_name",
    )
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("username", "first_name", "last_name")}),
        ("Access", {"fields": ("role", "account_status", "is_staff", "is_superuser")}),
        (
            "Email verification",
            {
                "fields": ("student_email", "email_verified", "student_email_verified"),
            },
        ),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "first_name",
                    "last_name",
                    "role",
                    "account_status",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = (
        "last_login",
        "date_joined",
        "student_email",
        "email_verified",
        "student_email_verified",
    )

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = User.objects.filter(pk=obj.pk).values_list(
                "account_status", flat=True
            ).first()
        super().save_model(request, obj, form, change)
        if (
            previous_status == User.AccountStatus.ACTIVE
            and not obj.is_active
        ):
            revoke_refresh_tokens(obj)


admin.site.register(StudentProfile)
admin.site.register(LecturerProfile)
admin.site.register(EmployerProfile)
