from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.models import EmployerProfile, User
from portfolios.models import StudentPortfolio
from portfolios.serializers import PublicPortfolioSerializer
from opportunities.models import (
    ApplicationAttachment,
    Opportunity,
    OpportunityApplication,
    OpportunityCategory,
    OpportunitySkill,
)


class OpportunityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OpportunityCategory
        fields = ("id", "name", "slug", "sort_order")
        read_only_fields = fields


class OpportunitySkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpportunitySkill
        fields = ("id", "name")
        read_only_fields = fields


class OpportunitySerializer(serializers.ModelSerializer):
    category = OpportunityCategorySerializer(read_only=True)
    required_skills = OpportunitySkillSerializer(many=True, read_only=True)
    is_applied = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "category",
            "title",
            "organization",
            "description",
            "responsibilities",
            "requirements",
            "required_skills",
            "location",
            "work_arrangement",
            "opportunity_type",
            "compensation",
            "application_deadline",
            "application_instructions",
            "status",
            "created_at",
            "published_at",
            "closes_at",
            "is_open",
            "is_applied",
        )
        read_only_fields = fields

    def get_is_applied(self, opportunity):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return OpportunityApplication.objects.filter(
            opportunity=opportunity, student=request.user
        ).exists()


class OpportunityWriteSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=OpportunityCategory.objects.filter(is_active=True)
    )
    required_skill_names = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        required=False,
        write_only=True,
        max_length=30,
    )

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "category",
            "title",
            "organization",
            "description",
            "responsibilities",
            "requirements",
            "required_skill_names",
            "location",
            "work_arrangement",
            "opportunity_type",
            "compensation",
            "application_deadline",
            "application_instructions",
            "status",
            "created_at",
            "updated_at",
            "published_at",
            "closes_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "published_at",
        )
        extra_kwargs = {
            "organization": {"required": False},
            "status": {"required": False},
        }

    def validate_required_skill_names(self, values):
        cleaned = []
        seen = set()
        for value in values:
            name = value.strip()
            if not name:
                raise serializers.ValidationError(
                    "Skill names cannot be blank."
                )
            normalized = name.casefold()
            if normalized not in seen:
                seen.add(normalized)
                cleaned.append(name)
        return cleaned

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        status_value = attrs.get(
            "status",
            self.instance.status if self.instance else Opportunity.PublicationStatus.DRAFT,
        )
        deadline = attrs.get(
            "application_deadline",
            self.instance.application_deadline if self.instance else None,
        )
        closes_at = attrs.get(
            "closes_at", self.instance.closes_at if self.instance else None
        )

        if status_value == Opportunity.PublicationStatus.PUBLISHED:
            if deadline is None or deadline <= timezone.now():
                raise serializers.ValidationError(
                    {
                        "application_deadline": (
                            "A published opportunity must have a future deadline."
                        )
                    }
                )
            if closes_at and closes_at <= timezone.now():
                raise serializers.ValidationError(
                    {"closes_at": "A published opportunity must not be past its closing date."}
                )
            if closes_at and closes_at < deadline:
                raise serializers.ValidationError(
                    {"closes_at": "The closing date must be on or after the deadline."}
                )

        if user.role in {User.Role.EMPLOYER, User.Role.RECRUITER}:
            try:
                organization = user.employer_profile.organization_name.strip()
            except EmployerProfile.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"organization": "An approved employer profile is required."}
                ) from exc
            supplied = attrs.get(
                "organization",
                self.instance.organization if self.instance else organization,
            )
            if supplied.strip().casefold() != organization.casefold():
                raise serializers.ValidationError(
                    {"organization": "Employer accounts may only post for their organization."}
                )
            attrs["organization"] = organization
        else:
            organization = attrs.get(
                "organization", self.instance.organization if self.instance else ""
            )
            organization = organization.strip()
            if not organization:
                raise serializers.ValidationError(
                    {"organization": "An organization name is required."}
                )
            attrs["organization"] = organization

        return attrs

    @staticmethod
    def _skills_for_names(names):
        skills = []
        for name in names:
            skill = OpportunitySkill.objects.filter(name__iexact=name).first()
            if skill is None:
                try:
                    with transaction.atomic():
                        skill = OpportunitySkill.objects.create(name=name)
                except IntegrityError:
                    skill = OpportunitySkill.objects.get(name__iexact=name)
            skills.append(skill)
        return skills

    @transaction.atomic
    def create(self, validated_data):
        skill_names = validated_data.pop("required_skill_names", [])
        opportunity = super().create(validated_data)
        opportunity.required_skills.set(self._skills_for_names(skill_names))
        return opportunity

    @transaction.atomic
    def update(self, instance, validated_data):
        skill_names = validated_data.pop("required_skill_names", None)
        opportunity = super().update(instance, validated_data)
        if skill_names is not None:
            opportunity.required_skills.set(self._skills_for_names(skill_names))
        return opportunity


class ApplicationAttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationAttachment
        fields = (
            "id",
            "file_name",
            "content_type",
            "file_size",
            "download_url",
            "uploaded_at",
        )
        read_only_fields = fields

    def get_download_url(self, attachment):
        from accounts.storage import create_signed_url

        return create_signed_url(
            "application_attachments", attachment.object_path
        )


class OpportunityApplicationCreateSerializer(serializers.ModelSerializer):
    portfolio = serializers.PrimaryKeyRelatedField(
        queryset=StudentPortfolio.objects.none(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = OpportunityApplication
        fields = ("portfolio", "statement")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["portfolio"].queryset = StudentPortfolio.objects.filter(
                student=request.user
            )

    def validate_statement(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "An application statement is required."
            )
        return value


class OpportunityApplicationSerializer(serializers.ModelSerializer):
    opportunity = OpportunitySerializer(read_only=True)
    portfolio_details = serializers.SerializerMethodField()
    attachments = ApplicationAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = OpportunityApplication
        fields = (
            "id",
            "opportunity",
            "portfolio_details",
            "statement",
            "attachments",
            "status",
            "submitted_at",
            "updated_at",
            "reviewed_at",
        )
        read_only_fields = fields

    def get_portfolio_details(self, application):
        if not application.portfolio_id:
            return None
        return PublicPortfolioSerializer(
            application.portfolio, context=self.context
        ).data


class ManagerOpportunityApplicationSerializer(OpportunityApplicationSerializer):
    student_name = serializers.SerializerMethodField()
    review_note = serializers.CharField(read_only=True)

    class Meta(OpportunityApplicationSerializer.Meta):
        fields = OpportunityApplicationSerializer.Meta.fields + (
            "student_name",
            "review_note",
        )

    def get_student_name(self, application):
        return application.student.get_full_name() or application.student.username


class OpportunityApplicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpportunityApplication
        fields = ("status", "review_note")

    def validate_status(self, value):
        if value == OpportunityApplication.Status.APPLIED:
            raise serializers.ValidationError(
                "An application decision cannot be reset to Applied."
            )
        return value
