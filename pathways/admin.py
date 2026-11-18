from django.contrib import admin

from pathways.models import (
    PathwayStep,
    PathwayStepProgress,
    Skill,
    SkillCategory,
    SkillPathway,
    StudentPathwayEnrollment,
)


class PathwayStepInline(admin.TabularInline):
    model = PathwayStep
    extra = 0


@admin.register(SkillPathway)
class SkillPathwayAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "difficulty",
        "status",
        "estimated_duration_weeks",
        "created_by",
    )
    list_filter = ("status", "difficulty", "category")
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("required_skills", "recommended_courses")
    inlines = [PathwayStepInline]


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "category__name")


@admin.register(StudentPathwayEnrollment)
class StudentPathwayEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("pathway", "student", "status", "enrolled_at", "completed_at")
    list_filter = ("status", "pathway")
    search_fields = ("pathway__name", "student__email", "student__username")


admin.site.register(PathwayStep)
admin.site.register(PathwayStepProgress)
