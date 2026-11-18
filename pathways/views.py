import logging
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from PIL import Image, UnidentifiedImageError
from rest_framework import generics, permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.storage import (
    SupabaseStorageError,
    create_signed_url,
    delete_private_file,
    upload_private_file,
)
from pathways.models import (
    PathwayStep,
    PathwayStepProgress,
    Skill,
    SkillCategory,
    SkillPathway,
    StudentPathwayEnrollment,
)
from pathways.permissions import IsActiveStudent, IsPathwayStaff
from pathways.serializers import (
    PathwayEnrollmentSerializer,
    PathwayProgressSerializer,
    PathwayStatisticsSerializer,
    PathwayStepSerializer,
    PathwayStepWriteSerializer,
    PathwayThumbnailUploadSerializer,
    SkillCategorySerializer,
    SkillPathwaySerializer,
    SkillPathwayWriteSerializer,
    SkillSerializer,
)


logger = logging.getLogger("pathways")


def _pathway_stats(queryset):
    return queryset.annotate(
        step_count=Count("steps", distinct=True),
        recommended_course_count=Count("recommended_courses", distinct=True),
        enrollment_count=Count("enrollments", distinct=True),
        completion_count=Count(
            "enrollments",
            filter=Q(enrollments__status=StudentPathwayEnrollment.Status.COMPLETED),
            distinct=True,
        ),
    )


def _manageable_pathways(user):
    pathways = SkillPathway.objects.all()
    if user.role == User.Role.ADMINISTRATOR:
        return pathways
    return pathways.filter(created_by=user)


class SkillCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = SkillCategorySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsPathwayStaff()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        categories = SkillCategory.objects.filter(is_active=True)
        if self.request.user.is_authenticated and self.request.user.role in {
            User.Role.LECTURER,
            User.Role.FACILITATOR,
            User.Role.ADMINISTRATOR,
        }:
            categories = SkillCategory.objects.all()
        return categories.annotate(
            pathway_count=Count(
                "pathways",
                filter=Q(pathways__status=SkillPathway.Status.PUBLISHED),
                distinct=True,
            )
        )


class SkillListView(generics.ListAPIView):
    serializer_class = SkillSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        skills = Skill.objects.filter(is_active=True, category__is_active=True)
        category = self.request.query_params.get("category")
        if category and category != "all":
            if category.isdigit():
                skills = skills.filter(category_id=category)
            else:
                skills = skills.filter(category__slug=category)
        return skills.select_related("category")


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter("search", str, description="Search pathway names and descriptions."),
            OpenApiParameter("category", str, description="Filter by category slug or ID."),
            OpenApiParameter(
                "difficulty",
                str,
                enum=[choice[0] for choice in SkillPathway.Difficulty.choices],
            ),
        ]
    )
)
class PathwayListView(generics.ListAPIView):
    serializer_class = SkillPathwaySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = _pathway_stats(
            SkillPathway.objects.filter(status=SkillPathway.Status.PUBLISHED)
            .select_related("category")
            .prefetch_related(
                "required_skills__category",
                "recommended_courses__category",
                "recommended_courses__instructors",
            )
        )
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        category = params.get("category")
        if category and category != "all":
            if category.isdigit():
                queryset = queryset.filter(category_id=category)
            else:
                queryset = queryset.filter(category__slug=category)
        difficulty = params.get("difficulty")
        if difficulty and difficulty != "all":
            queryset = queryset.filter(difficulty=difficulty)
        return queryset.order_by("category__sort_order", "name", "id")


class PathwayDetailView(generics.RetrieveAPIView):
    serializer_class = SkillPathwaySerializer
    permission_classes = [permissions.AllowAny]
    queryset = (
        SkillPathway.objects.filter(status=SkillPathway.Status.PUBLISHED)
        .select_related("category")
        .prefetch_related(
            "required_skills__category",
            "recommended_courses__category",
            "recommended_courses__instructors",
        )
    )

    def get_queryset(self):
        return _pathway_stats(super().get_queryset())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context["enrollment"] = StudentPathwayEnrollment.objects.filter(
                pathway_id=self.kwargs["pk"], student=self.request.user
            ).first()
        return context


class PathwayEnrollmentView(APIView):
    permission_classes = [IsActiveStudent]

    @extend_schema(
        request=None,
        responses={
            200: PathwayEnrollmentSerializer,
            201: PathwayEnrollmentSerializer,
        },
    )
    def post(self, request, pathway_id):
        pathway = get_object_or_404(
            SkillPathway, pk=pathway_id, status=SkillPathway.Status.PUBLISHED
        )
        try:
            with transaction.atomic():
                enrollment, created = StudentPathwayEnrollment.objects.get_or_create(
                    pathway=pathway, student=request.user
                )
        except IntegrityError:
            enrollment = StudentPathwayEnrollment.objects.get(
                pathway=pathway, student=request.user
            )
            created = False
        enrollment.pathway = _pathway_stats(
            SkillPathway.objects.filter(pk=pathway.pk).select_related("category")
        ).get()
        response_status = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(
            PathwayEnrollmentSerializer(enrollment).data, status=response_status
        )


class MyPathwaysView(generics.ListAPIView):
    serializer_class = PathwayEnrollmentSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return (
            StudentPathwayEnrollment.objects.filter(student=self.request.user)
            .select_related("pathway__category", "last_accessed_step")
            .prefetch_related(
                "pathway__required_skills__category",
                "pathway__recommended_courses__category",
                "pathway__recommended_courses__instructors",
            )
        )


class PathwayProgressView(generics.RetrieveAPIView):
    serializer_class = PathwayProgressSerializer
    permission_classes = [IsActiveStudent]
    lookup_url_kwarg = "pathway_id"

    def get_object(self):
        return get_object_or_404(
            StudentPathwayEnrollment.objects.select_related(
                "pathway__category", "last_accessed_step"
            ).prefetch_related(
                "pathway__required_skills__category",
                "pathway__recommended_courses__category",
                "pathway__recommended_courses__instructors",
            ),
            pathway_id=self.kwargs["pathway_id"],
            student=self.request.user,
        )


class CompletePathwayStepView(APIView):
    permission_classes = [IsActiveStudent]

    @extend_schema(request=None, responses={200: PathwayProgressSerializer})
    def post(self, request, pk):
        step = get_object_or_404(
            PathwayStep.objects.select_related("pathway"),
            pk=pk,
            pathway__status__in=[
                SkillPathway.Status.PUBLISHED,
                SkillPathway.Status.ARCHIVED,
            ],
        )
        enrollment = get_object_or_404(
            StudentPathwayEnrollment, pathway=step.pathway, student=request.user
        )
        now = timezone.now()
        with transaction.atomic():
            PathwayStepProgress.objects.update_or_create(
                enrollment=enrollment,
                step=step,
                defaults={"is_completed": True, "completed_at": now},
            )
            enrollment.last_accessed_step = step
            enrollment.last_accessed_at = now
            total_steps = PathwayStep.objects.filter(pathway=step.pathway).count()
            completed_steps = PathwayStepProgress.objects.filter(
                enrollment=enrollment, is_completed=True
            ).count()
            if total_steps and completed_steps == total_steps:
                enrollment.status = StudentPathwayEnrollment.Status.COMPLETED
                enrollment.completed_at = enrollment.completed_at or now
            enrollment.save(
                update_fields=[
                    "last_accessed_step",
                    "last_accessed_at",
                    "status",
                    "completed_at",
                ]
            )
        enrollment.pathway = _pathway_stats(
            SkillPathway.objects.filter(pk=step.pathway_id).select_related("category")
        ).get()
        return Response(PathwayProgressSerializer(enrollment).data)


class ManageSkillCategoryListCreateView(generics.ListCreateAPIView):
    queryset = SkillCategory.objects.all()
    serializer_class = SkillCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]


class ManageSkillListCreateView(generics.ListCreateAPIView):
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]

    def get_queryset(self):
        return Skill.objects.select_related("category").all()

    def perform_create(self, serializer):
        serializer.save()


class ManagePathwayListCreateView(generics.ListCreateAPIView):
    serializer_class = SkillPathwayWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]

    def get_queryset(self):
        return _manageable_pathways(self.request.user).select_related("category")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ManagePathwayDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SkillPathwayWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]
    lookup_url_kwarg = "pathway_id"

    def get_queryset(self):
        return _manageable_pathways(self.request.user).select_related("category")


class ManagePathwayStepsView(generics.ListCreateAPIView):
    serializer_class = PathwayStepWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]

    def get_pathway(self):
        return get_object_or_404(
            _manageable_pathways(self.request.user), pk=self.kwargs["pathway_id"]
        )

    def get_queryset(self):
        return self.get_pathway().steps.select_related(
            "recommended_course__category"
        )

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "pathway": self.get_pathway()}


class ManagePathwayStepDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PathwayStepWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]

    def get_queryset(self):
        return PathwayStep.objects.filter(
            pathway__in=_manageable_pathways(self.request.user)
        )


class ReorderPathwayStepsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]

    @extend_schema(
        request={"application/json": {"type": "object", "properties": {
            "step_ids": {"type": "array", "items": {"type": "integer"}}
        }, "required": ["step_ids"]}},
        responses={200: PathwayStepSerializer(many=True)},
    )
    def post(self, request, pathway_id):
        pathway = get_object_or_404(
            _manageable_pathways(request.user), pk=pathway_id
        )
        step_ids = request.data.get("step_ids")
        if not isinstance(step_ids, list) or any(
            isinstance(step_id, bool) or not isinstance(step_id, int)
            for step_id in step_ids
        ):
            raise serializers.ValidationError(
                {"step_ids": "Provide an ordered list of pathway step IDs."}
            )
        steps = list(pathway.steps.all())
        if len(step_ids) != len(steps) or set(step_ids) != {
            step.pk for step in steps
        }:
            raise serializers.ValidationError(
                {"step_ids": "Include each pathway step exactly once."}
            )
        step_by_id = {step.pk: step for step in steps}
        for order, step_id in enumerate(step_ids, start=1):
            step_by_id[step_id].order = order
        with transaction.atomic():
            PathwayStep.objects.bulk_update(steps, ["order"])
        ordered = pathway.steps.select_related("recommended_course__category")
        return Response(PathwayStepSerializer(ordered, many=True).data)


class ManagePathwayStatisticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]

    @extend_schema(responses={200: PathwayStatisticsSerializer})
    def get(self, request, pathway_id):
        pathway = get_object_or_404(
            _manageable_pathways(request.user), pk=pathway_id
        )
        enrollments = pathway.enrollments.all()
        return Response(
            {
                "enrollment_count": enrollments.count(),
                "in_progress_count": enrollments.filter(
                    status=StudentPathwayEnrollment.Status.IN_PROGRESS
                ).count(),
                "completed_count": enrollments.filter(
                    status=StudentPathwayEnrollment.Status.COMPLETED
                ).count(),
            }
        )


class ManagePathwayThumbnailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPathwayStaff]
    parser_classes = [MultiPartParser, FormParser]
    max_file_size = 5 * 1024 * 1024
    image_types = {
        "JPEG": ("jpg", "image/jpeg"),
        "PNG": ("png", "image/png"),
        "WEBP": ("webp", "image/webp"),
    }

    @extend_schema(
        request=PathwayThumbnailUploadSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {"thumbnail_url": {"type": "string", "format": "uri"}},
            }
        },
    )
    def post(self, request, pathway_id):
        pathway = get_object_or_404(
            _manageable_pathways(request.user), pk=pathway_id
        )
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
        except (
            UnidentifiedImageError,
            OSError,
            Image.DecompressionBombError,
        ) as exc:
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
        new_path = (
            f"pathways/{pathway.pk}/thumbnails/{uuid.uuid4().hex}.{extension}"
        )
        old_path = pathway.thumbnail_path
        stored_path = upload_private_file(
            "course_resources", new_path, thumbnail.read(), content_type
        )
        pathway.thumbnail_path = stored_path
        pathway.save(update_fields=["thumbnail_path", "updated_at"])
        if old_path:
            try:
                delete_private_file("course_resources", old_path)
            except SupabaseStorageError:
                logger.exception("Could not remove a replaced pathway thumbnail.")
        return Response(
            {"thumbnail_url": create_signed_url("course_resources", stored_path)},
            status=status.HTTP_200_OK,
        )
