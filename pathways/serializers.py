from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from accounts.storage import create_signed_url
from courses.models import Course
from courses.serializers import CourseCardSerializer
from pathways.models import (
    PathwayStep,
    PathwayStepProgress,
    Skill,
    SkillCategory,
    SkillPathway,
    StudentPathwayEnrollment,
)


class SkillCategorySerializer(serializers.ModelSerializer):
    pathway_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = SkillCategory
        fields = ("id", "name", "slug", "description", "sort_order", "pathway_count")
        read_only_fields = ("id", "pathway_count")
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}


class SkillSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Skill
        fields = ("id", "name", "slug", "description", "category", "category_name")
        read_only_fields = ("id", "slug", "category_name")


class PathwayStepSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    recommended_course = CourseCardSerializer(read_only=True)

    class Meta:
        model = PathwayStep
        fields = (
            "id",
            "title",
            "description",
            "order",
            "estimated_duration_weeks",
            "recommended_course",
            "project_title",
            "project_description",
            "is_completed",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_completed(self, step):
        enrollment = self.context.get("enrollment")
        if enrollment is None:
            return False
        return PathwayStepProgress.objects.filter(
            enrollment=enrollment, step=step, is_completed=True
        ).exists()


class SkillPathwaySerializer(serializers.ModelSerializer):
    category = SkillCategorySerializer(read_only=True)
    required_skills = SkillSerializer(many=True, read_only=True)
    recommended_courses = CourseCardSerializer(many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    step_count = serializers.IntegerField(read_only=True, default=0)
    recommended_course_count = serializers.IntegerField(read_only=True, default=0)
    enrollment_count = serializers.IntegerField(read_only=True, default=0)
    completion_count = serializers.IntegerField(read_only=True, default=0)
    steps = serializers.SerializerMethodField()

    class Meta:
        model = SkillPathway
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category",
            "difficulty",
            "estimated_duration_weeks",
            "thumbnail_url",
            "required_skills",
            "recommended_courses",
            "recommended_course_count",
            "step_count",
            "enrollment_count",
            "completion_count",
            "status",
            "steps",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_thumbnail_url(self, pathway):
        if not pathway.thumbnail_path:
            return None
        return create_signed_url("course_resources", pathway.thumbnail_path)

    @extend_schema_field(PathwayStepSerializer(many=True))
    def get_steps(self, pathway):
        enrollment = self.context.get("enrollment")
        steps = pathway.steps.select_related(
            "recommended_course__category"
        ).prefetch_related("recommended_course__instructors")
        return PathwayStepSerializer(
            steps, many=True, context={**self.context, "enrollment": enrollment}
        ).data


class SkillPathwayWriteSerializer(serializers.ModelSerializer):
    required_skill_ids = serializers.PrimaryKeyRelatedField(
        source="required_skills",
        queryset=Skill.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )
    recommended_course_ids = serializers.PrimaryKeyRelatedField(
        source="recommended_courses",
        queryset=Course.objects.filter(status=Course.Status.PUBLISHED),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = SkillPathway
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category",
            "difficulty",
            "estimated_duration_weeks",
            "thumbnail_path",
            "required_skill_ids",
            "recommended_course_ids",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "thumbnail_path", "created_by", "created_at", "updated_at")
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        status_value = attrs.get(
            "status", self.instance.status if self.instance else SkillPathway.Status.DRAFT
        )
        if status_value == SkillPathway.Status.PUBLISHED:
            pathway = self.instance
            if pathway is None:
                raise serializers.ValidationError(
                    {"status": "Create a draft and add steps before publishing."}
                )
            if not pathway.steps.exists():
                raise serializers.ValidationError(
                    {"status": "Add at least one step before publishing a pathway."}
                )
        return attrs


class PathwayStepWriteSerializer(serializers.ModelSerializer):
    recommended_course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.filter(status=Course.Status.PUBLISHED),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = PathwayStep
        fields = (
            "id",
            "title",
            "description",
            "order",
            "estimated_duration_weeks",
            "recommended_course",
            "project_title",
            "project_description",
        )
        read_only_fields = ("id",)
        extra_kwargs = {
            "order": {"required": False, "min_value": 1},
            "estimated_duration_weeks": {"required": False, "min_value": 1},
        }

    def create(self, validated_data):
        pathway = self.context["pathway"]
        validated_data.setdefault("order", pathway.steps.count() + 1)
        return PathwayStep.objects.create(pathway=pathway, **validated_data)


class PathwayEnrollmentSerializer(serializers.ModelSerializer):
    pathway = SkillPathwaySerializer(read_only=True)
    total_steps = serializers.SerializerMethodField()
    completed_steps = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    last_accessed_step_title = serializers.CharField(
        source="last_accessed_step.title", read_only=True, default=None
    )

    class Meta:
        model = StudentPathwayEnrollment
        fields = (
            "id",
            "pathway",
            "status",
            "total_steps",
            "completed_steps",
            "progress_percentage",
            "last_accessed_step",
            "last_accessed_step_title",
            "enrolled_at",
            "last_accessed_at",
            "completed_at",
        )
        read_only_fields = fields

    def _counts(self, enrollment):
        cached = getattr(enrollment, "_pathway_counts_cache", None)
        if cached is None:
            total = PathwayStep.objects.filter(pathway=enrollment.pathway).count()
            completed = PathwayStepProgress.objects.filter(
                enrollment=enrollment, is_completed=True
            ).count()
            cached = (total, completed)
            enrollment._pathway_counts_cache = cached
        return cached

    @extend_schema_field(serializers.IntegerField())
    def get_total_steps(self, enrollment):
        return self._counts(enrollment)[0]

    @extend_schema_field(serializers.IntegerField())
    def get_completed_steps(self, enrollment):
        return self._counts(enrollment)[1]

    @extend_schema_field(serializers.IntegerField())
    def get_progress_percentage(self, enrollment):
        total, completed = self._counts(enrollment)
        return round(completed * 100 / total) if total else 0


class PathwayProgressSerializer(PathwayEnrollmentSerializer):
    steps = serializers.SerializerMethodField()

    class Meta(PathwayEnrollmentSerializer.Meta):
        fields = PathwayEnrollmentSerializer.Meta.fields + ("steps",)

    @extend_schema_field(PathwayStepSerializer(many=True))
    def get_steps(self, enrollment):
        steps = enrollment.pathway.steps.select_related(
            "recommended_course__category"
        ).prefetch_related("recommended_course__instructors")
        return PathwayStepSerializer(
            steps,
            many=True,
            context={**self.context, "enrollment": enrollment},
        ).data


class PathwayStatisticsSerializer(serializers.Serializer):
    enrollment_count = serializers.IntegerField()
    in_progress_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()


class PathwayThumbnailUploadSerializer(serializers.Serializer):
    thumbnail = serializers.FileField()
