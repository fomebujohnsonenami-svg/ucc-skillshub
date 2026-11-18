from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from accounts.models import User
from accounts.storage import create_signed_url
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


UserModel = get_user_model()


class CourseCategorySerializer(serializers.ModelSerializer):
    course_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CourseCategory
        fields = ("id", "name", "slug", "description", "sort_order", "course_count")
        read_only_fields = ("id", "course_count")
        extra_kwargs = {
            "slug": {
                "required": False,
                "validators": [UniqueValidator(queryset=CourseCategory.objects.all())],
            }
        }


class InstructorSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = UserModel
        fields = ("id", "first_name", "last_name", "full_name")

    def get_full_name(self, user):
        return user.get_full_name() or user.username


class CourseCardSerializer(serializers.ModelSerializer):
    category = CourseCategorySerializer(read_only=True)
    instructors = InstructorSummarySerializer(many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    enrollment_count = serializers.IntegerField(read_only=True, default=0)
    average_rating = serializers.FloatField(read_only=True, default=0)
    review_count = serializers.IntegerField(read_only=True, default=0)
    lesson_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Course
        fields = (
            "id",
            "slug",
            "title",
            "description",
            "thumbnail_url",
            "category",
            "instructors",
            "difficulty",
            "estimated_duration_minutes",
            "learning_objectives",
            "prerequisites",
            "certificate_eligible",
            "status",
            "enrollment_count",
            "average_rating",
            "review_count",
            "lesson_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_thumbnail_url(self, course):
        if not course.thumbnail_path:
            return None
        return create_signed_url("course_resources", course.thumbnail_path)


class LessonOutlineSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            "id",
            "title",
            "description",
            "content_type",
            "duration_minutes",
            "order",
            "is_preview",
            "is_completed",
        )
        read_only_fields = fields

    def get_is_completed(self, lesson):
        enrollment = self.context.get("enrollment")
        if enrollment is None:
            return False
        return LessonProgress.objects.filter(
            enrollment=enrollment, lesson=lesson, is_completed=True
        ).exists()


class CourseModuleSerializer(serializers.ModelSerializer):
    lessons = LessonOutlineSerializer(many=True, read_only=True)

    class Meta:
        model = CourseModule
        fields = ("id", "title", "description", "order", "lessons")
        read_only_fields = fields


class CourseDetailSerializer(CourseCardSerializer):
    modules = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta(CourseCardSerializer.Meta):
        fields = CourseCardSerializer.Meta.fields + ("modules", "reviews")

    def get_modules(self, course):
        enrollment = self.context.get("enrollment")
        return CourseModuleSerializer(
            course.modules.prefetch_related("lessons").all(),
            many=True,
            context={**self.context, "enrollment": enrollment},
        ).data

    def get_reviews(self, course):
        return CourseReviewSerializer(
            course.reviews.select_related("student")[:10], many=True
        ).data


class CourseWriteSerializer(serializers.ModelSerializer):
    instructor_ids = serializers.PrimaryKeyRelatedField(
        queryset=UserModel.objects.filter(
            role__in=(User.Role.LECTURER, User.Role.FACILITATOR),
            account_status=User.AccountStatus.ACTIVE,
        ),
        many=True,
        required=False,
        write_only=True,
    )
    instructors = InstructorSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "thumbnail_path",
            "category",
            "instructors",
            "instructor_ids",
            "difficulty",
            "estimated_duration_minutes",
            "learning_objectives",
            "prerequisites",
            "status",
            "certificate_eligible",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "thumbnail_path": {"read_only": True},
        }

    def validate(self, attrs):
        request = self.context["request"]
        if "instructor_ids" in attrs and request.user.role != User.Role.ADMINISTRATOR:
            raise serializers.ValidationError(
                {"instructor_ids": "Only administrators can assign course instructors."}
            )
        if attrs.get("status") == Course.Status.PUBLISHED:
            course = self.instance
            if course and not course.modules.filter(lessons__isnull=False).exists():
                raise serializers.ValidationError(
                    {"status": "Add at least one lesson before publishing a course."}
                )
            if course is None and not attrs.get("allow_empty_publication", False):
                raise serializers.ValidationError(
                    {"status": "Create a draft and add lessons before publishing."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        instructors = validated_data.pop("instructor_ids", [])
        course = super().create(validated_data)
        if self.context["request"].user.role in {
            User.Role.LECTURER,
            User.Role.FACILITATOR,
        }:
            instructors = [self.context["request"].user]
        CourseInstructor.objects.bulk_create(
            [CourseInstructor(course=course, instructor=user) for user in instructors]
        )
        return course

    @transaction.atomic
    def update(self, instance, validated_data):
        instructors = validated_data.pop("instructor_ids", None)
        course = super().update(instance, validated_data)
        if instructors is not None:
            CourseInstructor.objects.filter(course=course).delete()
            CourseInstructor.objects.bulk_create(
                [
                    CourseInstructor(course=course, instructor=user)
                    for user in instructors
                ]
            )
        return course


class CourseModuleWriteSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(min_value=0, required=False)

    class Meta:
        model = CourseModule
        fields = ("id", "title", "description", "order")
        read_only_fields = ("id",)

    def create(self, validated_data):
        validated_data.setdefault("order", self.context["course"].modules.count())
        return CourseModule.objects.create(course=self.context["course"], **validated_data)


class LessonWriteSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(min_value=0, required=False)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "title",
            "description",
            "content_type",
            "content",
            "video_url",
            "duration_minutes",
            "order",
            "is_preview",
        )
        read_only_fields = ("id",)

    def validate_video_url(self, value):
        if value and not value.lower().startswith("https://"):
            raise serializers.ValidationError("Video URLs must use HTTPS.")
        return value

    def validate(self, attrs):
        content_type = attrs.get(
            "content_type",
            self.instance.content_type if self.instance else Lesson.ContentType.TEXT,
        )
        content = attrs.get("content", self.instance.content if self.instance else "")
        video_url = attrs.get(
            "video_url", self.instance.video_url if self.instance else ""
        )
        if content_type == Lesson.ContentType.TEXT and not content.strip():
            raise serializers.ValidationError(
                {"content": "Text lessons must include lesson content."}
            )
        if content_type == Lesson.ContentType.VIDEO and not video_url:
            raise serializers.ValidationError(
                {"video_url": "Video lessons must include an HTTPS video URL."}
            )
        return attrs

    def create(self, validated_data):
        module = self.context["module"]
        validated_data.setdefault("order", module.lessons.count())
        return Lesson.objects.create(module=module, **validated_data)


class CourseResourceSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = CourseResource
        fields = (
            "id",
            "title",
            "description",
            "content_type",
            "file_size",
            "download_url",
            "created_at",
        )
        read_only_fields = fields

    def get_download_url(self, resource):
        return create_signed_url("course_resources", resource.object_path)


class LessonDetailSerializer(serializers.ModelSerializer):
    module_title = serializers.CharField(source="module.title", read_only=True)
    course_id = serializers.IntegerField(source="module.course_id", read_only=True)
    previous_lesson_id = serializers.SerializerMethodField()
    next_lesson_id = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    resources = CourseResourceSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "course_id",
            "module_id",
            "module_title",
            "title",
            "description",
            "content_type",
            "content",
            "video_url",
            "duration_minutes",
            "order",
            "is_preview",
            "is_completed",
            "previous_lesson_id",
            "next_lesson_id",
            "resources",
        )
        read_only_fields = fields

    def _course_lessons(self, lesson):
        return Lesson.objects.filter(module__course_id=lesson.module.course_id).order_by(
            "module__order", "order", "id"
        )

    def get_previous_lesson_id(self, lesson):
        lessons = list(self._course_lessons(lesson).values_list("id", flat=True))
        index = lessons.index(lesson.id)
        return lessons[index - 1] if index > 0 else None

    def get_next_lesson_id(self, lesson):
        lessons = list(self._course_lessons(lesson).values_list("id", flat=True))
        index = lessons.index(lesson.id)
        return lessons[index + 1] if index + 1 < len(lessons) else None

    def get_is_completed(self, lesson):
        enrollment = self.context.get("enrollment")
        if enrollment is None:
            return False
        return LessonProgress.objects.filter(
            enrollment=enrollment, lesson=lesson, is_completed=True
        ).exists()


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    course = CourseCardSerializer(read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    total_lessons = serializers.SerializerMethodField()
    completed_lessons = serializers.SerializerMethodField()
    last_accessed_lesson_title = serializers.CharField(
        source="last_accessed_lesson.title", read_only=True, default=None
    )

    class Meta:
        model = CourseEnrollment
        fields = (
            "id",
            "course",
            "status",
            "progress_percentage",
            "total_lessons",
            "completed_lessons",
            "last_accessed_lesson",
            "last_accessed_lesson_title",
            "enrolled_at",
            "last_accessed_at",
            "completed_at",
        )
        read_only_fields = fields

    def _lesson_counts(self, enrollment):
        cached = getattr(enrollment, "_lesson_counts_cache", None)
        if cached is None:
            total = Lesson.objects.filter(module__course=enrollment.course).count()
            completed = LessonProgress.objects.filter(
                enrollment=enrollment, is_completed=True
            ).count()
            cached = (total, completed)
            enrollment._lesson_counts_cache = cached
        return cached

    def get_total_lessons(self, enrollment):
        return self._lesson_counts(enrollment)[0]

    def get_completed_lessons(self, enrollment):
        return self._lesson_counts(enrollment)[1]

    def get_progress_percentage(self, enrollment):
        total, completed = self._lesson_counts(enrollment)
        return round(completed * 100 / total) if total else 0


class CourseReviewSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = CourseReview
        fields = ("id", "student_name", "rating", "content", "created_at")
        read_only_fields = ("id", "student_name", "created_at")

    def get_student_name(self, review):
        return review.student.get_full_name() or review.student.username

    def validate_content(self, value):
        content = value.strip()
        if not content:
            raise serializers.ValidationError("Review content cannot be empty.")
        if len(content) > 2000:
            raise serializers.ValidationError("Review content cannot exceed 2000 characters.")
        return content

    def validate(self, attrs):
        if CourseReview.objects.filter(
            course=self.context["course"], student=self.context["request"].user
        ).exists():
            raise serializers.ValidationError(
                {"detail": "You have already reviewed this course."}
            )
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return CourseReview.objects.create(
                    course=self.context["course"],
                    student=self.context["request"].user,
                    **validated_data,
                )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"detail": "You have already reviewed this course."}
            ) from exc


class CourseManagementStatisticsSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    enrollment_count = serializers.IntegerField()
    in_progress_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()
