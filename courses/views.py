import logging
import mimetypes
import uuid
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from PIL import Image, UnidentifiedImageError
from rest_framework import generics, permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from certificates.services import award_achievements, issue_course_certificate
from accounts.storage import (
    SupabaseStorageError,
    create_signed_url,
    delete_private_file,
    upload_private_file,
)
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
from courses.permissions import IsActiveStudent, IsCourseStaff
from courses.serializers import (
    CourseCardSerializer,
    CourseCategorySerializer,
    CourseDetailSerializer,
    CourseEnrollmentSerializer,
    CourseManagementStatisticsSerializer,
    CourseModuleSerializer,
    CourseModuleWriteSerializer,
    CourseResourceSerializer,
    CourseReviewSerializer,
    CourseWriteSerializer,
    LessonDetailSerializer,
    LessonWriteSerializer,
)
from notifications.services import create_notification

logger = logging.getLogger("courses")


def _course_stats(queryset):
    return queryset.annotate(
        enrollment_count=Count("enrollments", distinct=True),
        average_rating=Avg("reviews__rating"),
        review_count=Count("reviews", distinct=True),
        lesson_count=Count("modules__lessons", distinct=True),
    )


def _manageable_courses(user):
    courses = Course.objects.all()
    if user.role == User.Role.ADMINISTRATOR:
        return courses
    return courses.filter(
        Q(created_by=user) | Q(course_instructors__instructor=user)
    ).distinct()


class CourseCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CourseCategorySerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsCourseStaff()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        categories = CourseCategory.objects.filter(is_active=True)
        if self.request.user.is_authenticated and self.request.user.role in {
            User.Role.LECTURER,
            User.Role.FACILITATOR,
            User.Role.ADMINISTRATOR,
        }:
            categories = CourseCategory.objects.all()
        return categories.annotate(
            course_count=Count(
                "courses",
                filter=Q(courses__status=Course.Status.PUBLISHED),
                distinct=True,
            )
        )


class CourseListView(generics.ListAPIView):
    serializer_class = CourseCardSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = _course_stats(
            Course.objects.filter(status=Course.Status.PUBLISHED)
            .select_related("category")
            .prefetch_related("instructors")
        )
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        category = params.get("category")
        if category and category != "all":
            if category.isdigit():
                queryset = queryset.filter(category_id=category)
            else:
                queryset = queryset.filter(category__slug=category)

        difficulty = params.get("difficulty") or params.get("level")
        if difficulty and difficulty != "all":
            queryset = queryset.filter(difficulty=difficulty)

        duration = params.get("duration")
        if duration == "short":
            queryset = queryset.filter(estimated_duration_minutes__lt=120)
        elif duration == "medium":
            queryset = queryset.filter(
                estimated_duration_minutes__gte=120,
                estimated_duration_minutes__lte=300,
            )
        elif duration == "long":
            queryset = queryset.filter(estimated_duration_minutes__gt=300)

        minimum = params.get("min_duration")
        maximum = params.get("max_duration")
        if minimum:
            try:
                queryset = queryset.filter(estimated_duration_minutes__gte=int(minimum))
            except ValueError:
                raise serializers.ValidationError(
                    {"min_duration": "Enter a whole number of minutes."}
                )
        if maximum:
            try:
                queryset = queryset.filter(estimated_duration_minutes__lte=int(maximum))
            except ValueError:
                raise serializers.ValidationError(
                    {"max_duration": "Enter a whole number of minutes."}
                )

        certificate = params.get("certificate")
        if certificate is not None:
            if certificate.lower() not in {"true", "false"}:
                raise serializers.ValidationError(
                    {"certificate": "Use true or false."}
                )
            queryset = queryset.filter(
                certificate_eligible=certificate.lower() == "true"
            )

        ordering = params.get("sort", params.get("ordering", "newest"))
        orderings = {
            "popular": ("-enrollment_count", "title"),
            "-popular": ("enrollment_count", "title"),
            "rated": ("-average_rating", "-review_count", "title"),
            "-rated": ("average_rating", "review_count", "title"),
            "newest": ("-created_at",),
            "-newest": ("created_at",),
            "duration": ("estimated_duration_minutes", "title"),
            "shortest": ("estimated_duration_minutes", "title"),
            "-duration": ("-estimated_duration_minutes", "title"),
            "longest": ("-estimated_duration_minutes", "title"),
            "title": ("title",),
            "-title": ("-title",),
        }
        if ordering not in orderings:
            raise serializers.ValidationError(
                {"sort": f"Unsupported course sort order: {ordering}."}
            )
        return queryset.order_by(*orderings[ordering])


class CourseDetailView(generics.RetrieveAPIView):
    serializer_class = CourseDetailSerializer
    permission_classes = [permissions.AllowAny]
    queryset = (
        Course.objects.filter(status=Course.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related("instructors", "modules__lessons", "reviews__student")
    )
    lookup_field = "pk"

    def get_queryset(self):
        return _course_stats(super().get_queryset())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context["enrollment"] = CourseEnrollment.objects.filter(
                course_id=self.kwargs["pk"], student=self.request.user
            ).first()
        return context


class MyCoursesView(generics.ListAPIView):
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return (
            CourseEnrollment.objects.filter(student=self.request.user)
            .select_related("course__category", "last_accessed_lesson")
            .prefetch_related("course__instructors")
        )


class CourseEnrollmentView(APIView):
    permission_classes = [IsActiveStudent]

    @extend_schema(
        responses={
            200: CourseEnrollmentSerializer,
            201: CourseEnrollmentSerializer,
        }
    )
    def post(self, request, course_id):
        course = get_object_or_404(
            Course, pk=course_id, status=Course.Status.PUBLISHED
        )
        try:
            with transaction.atomic():
                enrollment, created = CourseEnrollment.objects.get_or_create(
                    course=course, student=request.user
                )
        except IntegrityError:
            enrollment = CourseEnrollment.objects.get(
                course=course, student=request.user
            )
            created = False
        if created:
            create_notification(
                request.user,
                title="Course enrollment confirmed",
                message=f"You are enrolled in {course.title}.",
                notification_type="enrollment_confirmation",
                related_resource=enrollment,
                target_url="/courses/my-courses/",
            )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(CourseEnrollmentSerializer(enrollment).data, status=code)


class CourseModulesView(generics.ListAPIView):
    serializer_class = CourseModuleSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs["course_id"])
        if course.status != Course.Status.PUBLISHED and not (
            self.request.user.is_authenticated
            and _manageable_courses(self.request.user).filter(pk=course.pk).exists()
        ):
            return CourseModule.objects.none()
        return course.modules.prefetch_related("lessons").all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context["enrollment"] = CourseEnrollment.objects.filter(
                course_id=self.kwargs["course_id"], student=self.request.user
            ).first()
        return context


class LessonDetailView(generics.RetrieveAPIView):
    serializer_class = LessonDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Lesson.objects.select_related("module__course").prefetch_related(
        "resources"
    )

    def get_object(self):
        lesson = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        course = lesson.module.course
        user = self.request.user
        if _manageable_courses(user).filter(pk=course.pk).exists():
            return lesson

        enrollment = CourseEnrollment.objects.filter(
            course=course, student=user
        ).first()
        if course.status not in {Course.Status.PUBLISHED, Course.Status.ARCHIVED}:
            from rest_framework.exceptions import NotFound

            raise NotFound("This course is not available.")
        if enrollment is None and not lesson.is_preview:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Enroll in this course to access this lesson.")
        if enrollment:
            now = timezone.now()
            enrollment.last_accessed_lesson = lesson
            enrollment.last_accessed_at = now
            enrollment.save(
                update_fields=["last_accessed_lesson", "last_accessed_at"]
            )
            LessonProgress.objects.update_or_create(
                enrollment=enrollment,
                lesson=lesson,
                defaults={"last_accessed_at": now},
            )
            self._enrollment = enrollment
        return lesson

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["enrollment"] = getattr(self, "_enrollment", None)
        return context


class CompleteLessonView(APIView):
    permission_classes = [IsActiveStudent]

    @extend_schema(responses={200: CourseEnrollmentSerializer})
    def post(self, request, pk):
        lesson = get_object_or_404(
            Lesson.objects.select_related("module__course"),
            pk=pk,
            module__course__status__in=[
                Course.Status.PUBLISHED,
                Course.Status.ARCHIVED,
            ],
        )
        enrollment = get_object_or_404(
            CourseEnrollment, course=lesson.module.course, student=request.user
        )
        now = timezone.now()
        with transaction.atomic():
            progress, created = LessonProgress.objects.get_or_create(
                enrollment=enrollment,
                lesson=lesson,
                defaults={"is_completed": True, "completed_at": now},
            )
            newly_completed = created
            if not created and not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = now
                progress.save(update_fields=["is_completed", "completed_at"])
                newly_completed = True
            enrollment.last_accessed_lesson = lesson
            enrollment.last_accessed_at = now
            total_lessons = Lesson.objects.filter(
                module__course=enrollment.course
            ).count()
            completed_lessons = LessonProgress.objects.filter(
                enrollment=enrollment, is_completed=True
            ).count()
            if total_lessons and completed_lessons == total_lessons:
                enrollment.status = CourseEnrollment.Status.COMPLETED
                enrollment.completed_at = enrollment.completed_at or now
            enrollment.save(
                update_fields=[
                    "last_accessed_lesson",
                    "last_accessed_at",
                    "status",
                    "completed_at",
                ]
            )
        if newly_completed:
            create_notification(
                request.user,
                title="Learning progress updated",
                message=f"You completed {lesson.title}.",
                notification_type="learning_progress",
                related_resource=progress,
                target_url="/courses/my-courses/",
            )
        if enrollment.status == CourseEnrollment.Status.COMPLETED:
            issue_course_certificate(enrollment)
        award_achievements(
            request.user,
            event=(
                "course_completed"
                if enrollment.status == CourseEnrollment.Status.COMPLETED
                else "lesson_completed"
            ),
        )
        return Response(
            CourseEnrollmentSerializer(enrollment).data,
            status=status.HTTP_200_OK,
        )


class CourseReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = CourseReviewSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsActiveStudent()]
        return [permissions.AllowAny()]

    def get_course(self):
        return get_object_or_404(
            Course, pk=self.kwargs["course_id"], status=Course.Status.PUBLISHED
        )

    def get_queryset(self):
        return self.get_course().reviews.select_related("student")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["course"] = self.get_course()
        return context

    def perform_create(self, serializer):
        if not CourseEnrollment.objects.filter(
            course=self.get_course(), student=self.request.user
        ).exists():
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Enroll in this course before submitting a review.")
        serializer.save()


class ManageCourseListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    serializer_class = CourseWriteSerializer

    def get_queryset(self):
        return _manageable_courses(self.request.user).select_related(
            "category"
        ).prefetch_related("instructors")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ManageCourseDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    serializer_class = CourseWriteSerializer
    lookup_url_kwarg = "course_id"
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_queryset(self):
        return _manageable_courses(self.request.user).select_related(
            "category"
        ).prefetch_related("instructors")


class ManageCourseModulesView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    serializer_class = CourseModuleWriteSerializer

    def get_course(self):
        return get_object_or_404(
            _manageable_courses(self.request.user), pk=self.kwargs["course_id"]
        )

    def get_queryset(self):
        return self.get_course().modules.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["course"] = self.get_course()
        return context


class ManageModuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    serializer_class = CourseModuleWriteSerializer
    http_method_names = ["get", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        return CourseModule.objects.filter(
            course__in=_manageable_courses(self.request.user)
        )


class ManageModuleLessonsView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    serializer_class = LessonWriteSerializer

    def get_module(self):
        return get_object_or_404(
            CourseModule.objects.filter(
                course__in=_manageable_courses(self.request.user)
            ),
            pk=self.kwargs["module_id"],
        )

    def get_queryset(self):
        return self.get_module().lessons.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["module"] = self.get_module()
        return context


class ManageLessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    serializer_class = LessonWriteSerializer
    http_method_names = ["get", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        return Lesson.objects.filter(
            module__course__in=_manageable_courses(self.request.user)
        )


class ManageLessonResourceUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    parser_classes = [MultiPartParser, FormParser]
    max_file_size = 50 * 1024 * 1024
    allowed_extensions = {
        ".csv",
        ".doc",
        ".docx",
        ".jpg",
        ".jpeg",
        ".mp4",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".txt",
        ".webp",
        ".xls",
        ".xlsx",
        ".zip",
    }

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["file", "title"],
            }
        },
        responses={201: CourseResourceSerializer},
    )
    def post(self, request, lesson_id):
        lesson = get_object_or_404(
            Lesson.objects.filter(
                module__course__in=_manageable_courses(request.user)
            ),
            pk=lesson_id,
        )
        uploaded_file = request.FILES.get("file")
        title = request.data.get("title", "").strip()
        if not uploaded_file or not title:
            raise serializers.ValidationError(
                {"file": "A file and a resource title are required."}
            )
        if uploaded_file.size > self.max_file_size:
            raise serializers.ValidationError(
                {"file": "Course resources must be 50 MB or smaller."}
            )
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in self.allowed_extensions:
            raise serializers.ValidationError(
                {"file": "This file type is not permitted as a course resource."}
            )
        content_type = uploaded_file.content_type or "application/octet-stream"
        expected_content_type, _ = mimetypes.guess_type(
            f"resource{extension}", strict=False
        )
        if (
            expected_content_type
            and content_type not in {expected_content_type, "application/octet-stream"}
        ):
            raise serializers.ValidationError(
                {"file": "The declared file type does not match its extension."}
            )
        object_path = (
            f"courses/{lesson.module.course_id}/lessons/{lesson.pk}/"
            f"{uuid.uuid4().hex}{extension}"
        )
        stored_path = upload_private_file(
            "course_resources",
            object_path,
            uploaded_file.read(),
            content_type,
        )
        try:
            resource = CourseResource.objects.create(
                lesson=lesson,
                title=title[:200],
                description=request.data.get("description", "").strip()[:500],
                object_path=stored_path,
                content_type=content_type,
                file_size=uploaded_file.size,
                uploaded_by=request.user,
            )
        except IntegrityError:
            try:
                delete_private_file("course_resources", stored_path)
            except SupabaseStorageError:
                logger.exception("Could not remove an unrecorded course resource.")
            raise
        return Response(
            CourseResourceSerializer(resource).data,
            status=status.HTTP_201_CREATED,
        )


class ManageCourseThumbnailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]
    parser_classes = [MultiPartParser, FormParser]
    max_file_size = 5 * 1024 * 1024
    image_types = {
        "JPEG": ("jpg", "image/jpeg"),
        "PNG": ("png", "image/png"),
        "WEBP": ("webp", "image/webp"),
    }

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"thumbnail": {"type": "string", "format": "binary"}},
                "required": ["thumbnail"],
            }
        },
        responses={200: CourseCardSerializer},
    )
    def post(self, request, course_id):
        course = get_object_or_404(_manageable_courses(request.user), pk=course_id)
        thumbnail = request.FILES.get("thumbnail")
        if not thumbnail:
            raise serializers.ValidationError(
                {"thumbnail": "A thumbnail image is required."}
            )
        if thumbnail.size > self.max_file_size:
            raise serializers.ValidationError(
                {"thumbnail": "Thumbnails must be 5 MB or smaller."}
            )
        try:
            image = Image.open(thumbnail)
            image_format = image.format
            width, height = image.size
            image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise serializers.ValidationError(
                {"thumbnail": "Upload a valid JPEG, PNG, or WebP image."}
            ) from exc
        if image_format not in self.image_types or width * height > 20_000_000:
            raise serializers.ValidationError(
                {"thumbnail": "Upload a valid JPEG, PNG, or WebP image."}
            )
        extension, content_type = self.image_types[image_format]
        if thumbnail.content_type and thumbnail.content_type != content_type:
            raise serializers.ValidationError(
                {"thumbnail": "The file content does not match its image type."}
            )
        thumbnail.seek(0)
        new_path = f"courses/{course.pk}/thumbnails/{uuid.uuid4().hex}.{extension}"
        old_path = course.thumbnail_path
        stored_path = upload_private_file(
            "course_resources", new_path, thumbnail.read(), content_type
        )
        course.thumbnail_path = stored_path
        course.save(update_fields=["thumbnail_path", "updated_at"])
        if old_path:
            try:
                delete_private_file("course_resources", old_path)
            except SupabaseStorageError:
                logger.exception("Could not remove a replaced course thumbnail.")
        course = _course_stats(
            Course.objects.filter(pk=course.pk)
            .select_related("category")
            .prefetch_related("instructors")
        ).get()
        return Response(CourseCardSerializer(course).data, status=status.HTTP_200_OK)


class ManageCourseStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCourseStaff]

    @extend_schema(responses={200: CourseManagementStatisticsSerializer})
    def get(self, request, course_id):
        course = get_object_or_404(_manageable_courses(request.user), pk=course_id)
        rating = course.reviews.aggregate(
            average_rating=Avg("rating"), review_count=Count("id")
        )
        data = {
            "course_id": course.pk,
            "enrollment_count": course.enrollments.count(),
            "in_progress_count": course.enrollments.filter(
                status=CourseEnrollment.Status.IN_PROGRESS
            ).count(),
            "completed_count": course.enrollments.filter(
                status=CourseEnrollment.Status.COMPLETED
            ).count(),
            **rating,
        }
        return Response(
            CourseManagementStatisticsSerializer(data).data,
            status=status.HTTP_200_OK,
        )
