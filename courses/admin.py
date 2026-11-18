from django.contrib import admin

from courses.models import (
    Course,
    CourseCategory,
    CourseEnrollment,
    CourseInstructor,
    CourseModule,
    CourseResource,
    CourseReview,
    Lesson,
    LessonProgress,
)


class CourseInstructorInline(admin.TabularInline):
    model = CourseInstructor
    extra = 0


class CourseModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "difficulty",
        "status",
        "certificate_eligible",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "difficulty", "category", "certificate_eligible")
    search_fields = ("title", "description", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CourseInstructorInline, CourseModuleInline]


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "updated_at")
    list_filter = ("course",)
    search_fields = ("title", "course__title")
    inlines = [LessonInline]


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("course", "student", "status", "enrolled_at", "completed_at")
    list_filter = ("status", "course")
    search_fields = ("course__title", "student__email", "student__username")


admin.site.register(Lesson)
admin.site.register(LessonProgress)
admin.site.register(CourseReview)
admin.site.register(CourseResource)
