from django.contrib import admin

# Register your models here.
from django.contrib import admin

from opportunities.models import (
    ApplicationAttachment,
    Opportunity,
    OpportunityApplication,
    OpportunityCategory,
    OpportunitySkill,
)


@admin.register(OpportunityCategory)
class OpportunityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OpportunitySkill)
class OpportunitySkillAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "category",
        "status",
        "application_deadline",
        "created_by",
    )
    list_filter = ("status", "category", "work_arrangement")
    search_fields = ("title", "organization", "location")
    filter_horizontal = ("required_skills",)
    readonly_fields = ("created_at", "updated_at", "published_at")


class ApplicationAttachmentInline(admin.TabularInline):
    model = ApplicationAttachment
    extra = 0
    readonly_fields = (
        "file_name",
        "object_path",
        "content_type",
        "file_size",
        "uploaded_by",
        "uploaded_at",
    )
    can_delete = False


@admin.register(OpportunityApplication)
class OpportunityApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "opportunity",
        "student",
        "status",
        "submitted_at",
        "reviewed_by",
    )
    list_filter = ("status", "submitted_at")
    search_fields = (
        "opportunity__title",
        "opportunity__organization",
        "student__email",
        "student__first_name",
        "student__last_name",
    )
    readonly_fields = (
        "opportunity",
        "student",
        "portfolio",
        "statement",
        "submitted_at",
        "updated_at",
    )
    inlines = (ApplicationAttachmentInline,)

    def has_delete_permission(self, request, obj=None):
        return False
