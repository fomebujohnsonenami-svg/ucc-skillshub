from django.contrib import admin

from certificates.models import Achievement, Certificate, StudentAchievement


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_id",
        "student",
        "course",
        "pathway",
        "issue_date",
        "is_revoked",
    )
    list_filter = ("is_revoked", "issue_date")
    search_fields = ("certificate_id", "student__email", "verification_token")
    readonly_fields = (
        "certificate_id",
        "verification_token",
        "issue_date",
        "certificate_file",
        "student",
        "course",
        "pathway",
        "issuing_organization",
        "completion_info",
    )

    def has_add_permission(self, request):
        return False


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "key", "description")


@admin.register(StudentAchievement)
class StudentAchievementAdmin(admin.ModelAdmin):
    list_display = ("student", "achievement", "awarded_at")
    list_filter = ("achievement__category", "awarded_at")
    search_fields = ("student__email", "achievement__name")
    readonly_fields = ("awarded_at",)
