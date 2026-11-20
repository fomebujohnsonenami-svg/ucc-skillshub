from django.contrib import admin

from portfolios.models import (
    PortfolioCertificate,
    PortfolioProject,
    PortfolioSkill,
    PortfolioSocialLink,
    StudentPortfolio,
)


class PortfolioSkillInline(admin.TabularInline):
    model = PortfolioSkill
    extra = 0


class PortfolioProjectInline(admin.TabularInline):
    model = PortfolioProject
    extra = 0


@admin.register(StudentPortfolio)
class StudentPortfolioAdmin(admin.ModelAdmin):
    list_display = ("student", "slug", "is_public", "updated_at")
    list_filter = ("is_public", "updated_at")
    search_fields = ("student__username", "student__email", "slug", "headline")
    readonly_fields = ("slug", "created_at", "updated_at")
    inlines = (PortfolioSkillInline, PortfolioProjectInline)


@admin.register(PortfolioCertificate)
class PortfolioCertificateAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "certificate", "created_at")
    search_fields = ("portfolio__student__email", "certificate__certificate_id")
    readonly_fields = ("created_at",)


@admin.register(PortfolioSocialLink)
class PortfolioSocialLinkAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "label", "platform", "url")
    list_filter = ("platform",)
    search_fields = ("portfolio__student__email", "label", "url")
