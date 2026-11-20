from urllib.parse import urlencode, urlsplit, urlunsplit

from django.conf import settings
from rest_framework import serializers

from accounts.storage import create_signed_url
from certificates.models import Certificate
from portfolios.models import (
    PortfolioCertificate,
    PortfolioProject,
    PortfolioSkill,
    PortfolioSocialLink,
    StudentPortfolio,
)


class PortfolioSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioSkill
        fields = ("id", "name", "proficiency", "category", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A skill name is required.")
        request = self.context.get("request")
        portfolio = (
            StudentPortfolio.objects.filter(student=request.user).first()
            if request and request.user.is_authenticated
            else None
        )
        queryset = PortfolioSkill.objects.filter(portfolio=portfolio, name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if portfolio and queryset.exists():
            raise serializers.ValidationError("This skill is already in your portfolio.")
        return value


class PortfolioProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioProject
        fields = (
            "id",
            "title",
            "description",
            "role",
            "category",
            "skills",
            "repository_url",
            "demo_url",
            "image_url",
            "is_featured",
            "is_public",
            "display_order",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_skills(self, value):
        if not isinstance(value, list) or any(
            not isinstance(skill, str) or not skill.strip() for skill in value
        ):
            raise serializers.ValidationError(
                "Skills must be a list of non-empty strings."
            )
        if len(value) > 30 or any(len(skill) > 100 for skill in value):
            raise serializers.ValidationError(
                "Provide no more than 30 skills, each 100 characters or fewer."
            )
        return [skill.strip() for skill in value]

    def _validate_http_url(self, value, field):
        if value and not value.lower().startswith(("https://", "http://")):
            raise serializers.ValidationError(f"{field} must use HTTP or HTTPS.")
        return value

    def validate_repository_url(self, value):
        return self._validate_http_url(value, "Repository URLs")

    def validate_demo_url(self, value):
        return self._validate_http_url(value, "Demo URLs")

    def validate_image_url(self, value):
        return self._validate_http_url(value, "Image URLs")


class PortfolioSocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioSocialLink
        fields = (
            "id",
            "platform",
            "label",
            "url",
            "display_order",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A link label is required.")
        return value

    def validate_url(self, value):
        if not value.lower().startswith(("https://", "http://")):
            raise serializers.ValidationError("Links must use HTTP or HTTPS.")
        request = self.context.get("request")
        portfolio = (
            StudentPortfolio.objects.filter(student=request.user).first()
            if request and request.user.is_authenticated
            else None
        )
        if portfolio:
            links = PortfolioSocialLink.objects.filter(
                portfolio=portfolio, url=value
            )
            if self.instance:
                links = links.exclude(pk=self.instance.pk)
            if links.exists():
                raise serializers.ValidationError(
                    "This link is already in your portfolio."
                )
        return value


class PortfolioCertificateInfoSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SerializerMethodField()
    learning_item = serializers.SerializerMethodField()
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "id",
            "certificate_id",
            "certificate_type",
            "learning_item",
            "issuing_organization",
            "issue_date",
            "verification_url",
        )
        read_only_fields = fields

    def get_certificate_type(self, certificate):
        return "course" if certificate.course_id else "pathway"

    def get_learning_item(self, certificate):
        return certificate.course.title if certificate.course_id else certificate.pathway.name

    def get_verification_url(self, certificate):
        request = self.context.get("request")
        url = f"/certificates/verify/{certificate.verification_token}/"
        return request.build_absolute_uri(url) if request else url


class PortfolioCertificateSerializer(serializers.ModelSerializer):
    certificate = serializers.PrimaryKeyRelatedField(
        queryset=Certificate.objects.none(), write_only=True
    )
    certificate_details = PortfolioCertificateInfoSerializer(
        source="certificate", read_only=True
    )

    class Meta:
        model = PortfolioCertificate
        fields = ("id", "certificate", "certificate_details", "created_at")
        read_only_fields = ("id", "created_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["certificate"].queryset = Certificate.objects.filter(
                student=request.user, is_revoked=False
            )

    def validate(self, attrs):
        certificate = attrs.get(
            "certificate",
            self.instance.certificate if self.instance else None,
        )
        request = self.context.get("request")
        if certificate and (
            request is None or certificate.student_id != request.user.pk
        ):
            raise serializers.ValidationError(
                {"certificate": "Only your own earned certificates can be showcased."}
            )
        portfolio = (
            StudentPortfolio.objects.filter(student=request.user).first()
            if request and request.user.is_authenticated
            else None
        )
        if (
            certificate
            and portfolio
            and PortfolioCertificate.objects.filter(
                portfolio=portfolio, certificate=certificate
            )
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise serializers.ValidationError(
                {"certificate": "This certificate is already showcased."}
            )
        return attrs


class AvailableCertificateSerializer(PortfolioCertificateInfoSerializer):
    pass


class StudentPortfolioSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()
    skills = PortfolioSkillSerializer(many=True, read_only=True)
    projects = PortfolioProjectSerializer(many=True, read_only=True)
    certificates = serializers.SerializerMethodField()
    available_certificates = serializers.SerializerMethodField()
    social_links = PortfolioSocialLinkSerializer(many=True, read_only=True)

    class Meta:
        model = StudentPortfolio
        fields = (
            "id",
            "slug",
            "full_name",
            "headline",
            "biography",
            "academic_programme",
            "location",
            "profile_photo_url",
            "github_url",
            "linkedin_url",
            "is_public",
            "public_url",
            "skills",
            "projects",
            "certificates",
            "available_certificates",
            "social_links",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "full_name",
            "profile_photo_url",
            "public_url",
            "skills",
            "projects",
            "certificates",
            "available_certificates",
            "social_links",
            "created_at",
            "updated_at",
        )

    def validate_github_url(self, value):
        return self._validate_http_url(value, "GitHub URLs")

    def validate_linkedin_url(self, value):
        return self._validate_http_url(value, "LinkedIn URLs")

    def _validate_http_url(self, value, field):
        if value and not value.lower().startswith(("https://", "http://")):
            raise serializers.ValidationError(f"{field} must use HTTP or HTTPS.")
        return value

    def get_full_name(self, portfolio):
        return portfolio.student.get_full_name() or portfolio.student.username

    def get_profile_photo_url(self, portfolio):
        if not portfolio.student.profile_photo_path:
            return None
        return create_signed_url(
            "profile_photos", portfolio.student.profile_photo_path
        )

    def get_public_url(self, portfolio):
        frontend_url = settings.FRONTEND_BASE_URL
        if frontend_url:
            parts = urlsplit(frontend_url)
            return urlunsplit(
                (
                    parts.scheme,
                    parts.netloc,
                    "/skillbridge_student_portfolio/code.html",
                    urlencode({"slug": portfolio.slug}),
                    "",
                )
            )
        return f"/skillbridge_student_portfolio/code.html?{urlencode({'slug': portfolio.slug})}"

    def get_certificates(self, portfolio):
        links = portfolio.certificates.filter(certificate__is_revoked=False).select_related(
            "certificate__course", "certificate__pathway"
        )
        return PortfolioCertificateSerializer(
            links, many=True, context=self.context
        ).data

    def get_available_certificates(self, portfolio):
        certificates = Certificate.objects.filter(
            student=portfolio.student, is_revoked=False
        ).exclude(portfolio_entries__portfolio=portfolio).select_related(
            "course", "pathway"
        )
        return AvailableCertificateSerializer(
            certificates, many=True, context=self.context
        ).data


class PublicPortfolioSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField()
    skills = PortfolioSkillSerializer(many=True, read_only=True)
    projects = serializers.SerializerMethodField()
    certificates = serializers.SerializerMethodField()
    social_links = PortfolioSocialLinkSerializer(many=True, read_only=True)

    class Meta:
        model = StudentPortfolio
        fields = (
            "slug",
            "full_name",
            "headline",
            "biography",
            "academic_programme",
            "location",
            "profile_photo_url",
            "github_url",
            "linkedin_url",
            "skills",
            "projects",
            "certificates",
            "social_links",
        )
        read_only_fields = fields

    def get_full_name(self, portfolio):
        return portfolio.student.get_full_name() or portfolio.student.username

    def get_profile_photo_url(self, portfolio):
        if not portfolio.student.profile_photo_path:
            return None
        return create_signed_url(
            "profile_photos", portfolio.student.profile_photo_path
        )

    def get_projects(self, portfolio):
        return PortfolioProjectSerializer(
            portfolio.projects.filter(is_public=True), many=True, context=self.context
        ).data

    def get_certificates(self, portfolio):
        links = portfolio.certificates.filter(certificate__is_revoked=False).select_related(
            "certificate__course", "certificate__pathway"
        )
        return PortfolioCertificateSerializer(
            links, many=True, context=self.context
        ).data
