import logging
import uuid
from pathlib import PurePosixPath

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.storage import (
    SupabaseStorageError,
    delete_private_file,
    upload_private_file,
)
from courses.permissions import IsActiveStudent
from opportunities.models import (
    ApplicationAttachment,
    Opportunity,
    OpportunityApplication,
    OpportunityCategory,
)
from opportunities.permissions import IsOpportunityManager, is_opportunity_manager
from opportunities.serializers import (
    ManagerOpportunityApplicationSerializer,
    OpportunityApplicationCreateSerializer,
    OpportunityApplicationSerializer,
    OpportunityApplicationStatusSerializer,
    OpportunityCategorySerializer,
    OpportunitySerializer,
    OpportunityWriteSerializer,
)
from notifications.services import create_notification, notify_students


logger = logging.getLogger(__name__)

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_APPLICATION = 5
ALLOWED_ATTACHMENT_TYPES = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
}


def _has_valid_file_signature(extension, uploaded):
    header = uploaded.read(8192)
    uploaded.seek(0)
    signatures = {
        ".doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
        ".docx": b"PK\x03\x04",
        ".jpeg": b"\xff\xd8\xff",
        ".jpg": b"\xff\xd8\xff",
        ".pdf": b"%PDF-",
        ".png": b"\x89PNG\r\n\x1a\n",
    }
    if extension == ".rtf":
        return header.lstrip().startswith(b"{\\rtf")
    if extension == ".txt":
        return b"\x00" not in header
    return header.startswith(signatures[extension])


class OpportunityCategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = OpportunityCategorySerializer
    queryset = OpportunityCategory.objects.filter(is_active=True)


class OpportunityListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = OpportunitySerializer
    queryset = Opportunity.objects.none()

    def get_queryset(self):
        now = timezone.now()
        queryset = (
            Opportunity.objects.filter(
                status=Opportunity.PublicationStatus.PUBLISHED,
                application_deadline__gt=now,
            )
            .filter(Q(closes_at__isnull=True) | Q(closes_at__gt=now))
            .select_related("category", "created_by")
            .prefetch_related("required_skills")
        )

        search = (
            self.request.query_params.get("search")
            or self.request.query_params.get("q")
            or ""
        ).strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(organization__icontains=search)
            )

        category = self.request.query_params.get("category", "").strip()
        if category:
            if category.isdigit():
                queryset = queryset.filter(category_id=category)
            else:
                queryset = queryset.filter(category__slug__iexact=category)

        location = self.request.query_params.get("location", "").strip()
        if location:
            queryset = queryset.filter(location__icontains=location)

        skills = self.request.query_params.get("skills", "")
        skill_terms = [skill.strip() for skill in skills.split(",") if skill.strip()]
        if skill_terms:
            skill_filter = Q()
            for skill in skill_terms:
                skill_filter |= Q(required_skills__name__iexact=skill)
            queryset = queryset.filter(skill_filter).distinct()

        arrangement = (
            self.request.query_params.get("work_arrangement")
            or self.request.query_params.get("arrangement")
            or ""
        ).strip().lower()
        if arrangement:
            queryset = queryset.filter(work_arrangement=arrangement)

        opportunity_type = self.request.query_params.get(
            "opportunity_type", ""
        ).strip()
        if opportunity_type:
            queryset = queryset.filter(opportunity_type__iexact=opportunity_type)

        deadline_before = self.request.query_params.get("deadline_before", "").strip()
        if deadline_before:
            parsed_deadline = parse_date(deadline_before)
            if parsed_deadline is None:
                raise serializers.ValidationError(
                    {"deadline_before": "Use an ISO date in YYYY-MM-DD format."}
                )
            queryset = queryset.filter(application_deadline__date__lte=parsed_deadline)

        deadline_after = self.request.query_params.get("deadline_after", "").strip()
        if deadline_after:
            parsed_deadline = parse_date(deadline_after)
            if parsed_deadline is None:
                raise serializers.ValidationError(
                    {"deadline_after": "Use an ISO date in YYYY-MM-DD format."}
                )
            queryset = queryset.filter(application_deadline__date__gte=parsed_deadline)

        return queryset


class OpportunityDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = OpportunitySerializer
    queryset = Opportunity.objects.filter(
        status=Opportunity.PublicationStatus.PUBLISHED
    ).select_related("category").prefetch_related("required_skills")


class OpportunityManagerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsOpportunityManager]

    def get_queryset(self):
        queryset = Opportunity.objects.select_related("category", "created_by").prefetch_related(
            "required_skills"
        )
        if self.request.user.role == User.Role.ADMINISTRATOR:
            return queryset
        organization = self.request.user.employer_profile.organization_name
        return queryset.filter(organization__iexact=organization)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OpportunityWriteSerializer
        return OpportunitySerializer

    def perform_create(self, serializer):
        opportunity = serializer.save(created_by=self.request.user)
        if opportunity.status == Opportunity.PublicationStatus.PUBLISHED:
            notify_students(
                title="New opportunity",
                message=f"{opportunity.title} is now open at {opportunity.organization}.",
                notification_type="new_opportunity",
                related_resource=opportunity,
                target_url=f"/opportunities/{opportunity.pk}/",
            )


class OpportunityManagerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsOpportunityManager]
    http_method_names = ("get", "patch", "put", "head", "options")

    def get_queryset(self):
        queryset = Opportunity.objects.select_related("category", "created_by").prefetch_related(
            "required_skills"
        )
        if self.request.user.role == User.Role.ADMINISTRATOR:
            return queryset
        organization = self.request.user.employer_profile.organization_name
        return queryset.filter(organization__iexact=organization)

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return OpportunityWriteSerializer
        return OpportunitySerializer

    def perform_update(self, serializer):
        was_published = (
            serializer.instance.status == Opportunity.PublicationStatus.PUBLISHED
        )
        opportunity = serializer.save()
        if (
            opportunity.status == Opportunity.PublicationStatus.PUBLISHED
            and not was_published
        ):
            notify_students(
                title="New opportunity",
                message=f"{opportunity.title} is now open at {opportunity.organization}.",
                notification_type="new_opportunity",
                related_resource=opportunity,
                target_url=f"/opportunities/{opportunity.pk}/",
            )


class OpportunityApplyView(APIView):
    permission_classes = [IsActiveStudent]

    def post(self, request, pk):
        serializer = OpportunityApplicationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        files = request.FILES.getlist("attachments")
        if len(files) > MAX_ATTACHMENTS_PER_APPLICATION:
            raise serializers.ValidationError(
                {
                    "attachments": (
                        f"You can upload at most {MAX_ATTACHMENTS_PER_APPLICATION} files."
                    )
                }
            )

        validated_files = []
        for uploaded in files:
            extension = PurePosixPath(
                uploaded.name.replace("\\", "/")
            ).suffix.lower()
            expected_type = ALLOWED_ATTACHMENT_TYPES.get(extension)
            if not expected_type:
                raise serializers.ValidationError(
                    {"attachments": f"{uploaded.name} has an unsupported file type."}
                )
            if uploaded.size == 0:
                raise serializers.ValidationError(
                    {"attachments": f"{uploaded.name} is empty."}
                )
            if uploaded.size > MAX_ATTACHMENT_SIZE:
                raise serializers.ValidationError(
                    {
                        "attachments": (
                            f"{uploaded.name} exceeds the 10 MB per-file limit."
                        )
                    }
                )
            content_type = uploaded.content_type or ""
            if content_type not in ("", "application/octet-stream", expected_type):
                raise serializers.ValidationError(
                    {"attachments": f"{uploaded.name} has an invalid content type."}
                )
            if not _has_valid_file_signature(extension, uploaded):
                raise serializers.ValidationError(
                    {"attachments": f"{uploaded.name} does not match its file type."}
                )
            validated_files.append((uploaded, extension, expected_type))

        try:
            with transaction.atomic():
                opportunity = get_object_or_404(
                    Opportunity.objects.select_for_update().select_related("category"),
                    pk=pk,
                )
                if not opportunity.is_open:
                    return Response(
                        {"detail": "This opportunity is no longer accepting applications."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if OpportunityApplication.objects.filter(
                    opportunity=opportunity, student=request.user
                ).exists():
                    return Response(
                        {"detail": "You have already applied to this opportunity."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                application = serializer.save(
                    opportunity=opportunity, student=request.user
                )
        except IntegrityError:
            return Response(
                {"detail": "You have already applied to this opportunity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        object_paths = []
        try:
            for uploaded, extension, content_type in validated_files:
                file_name = PurePosixPath(
                    uploaded.name.replace("\\", "/")
                ).name[:255]
                object_path = (
                    f"applications/{application.pk}/{uuid.uuid4().hex}{extension}"
                )
                object_paths.append(object_path)
                uploaded.seek(0)
                upload_private_file(
                    "application_attachments",
                    object_path,
                    uploaded.read(),
                    content_type,
                )
                ApplicationAttachment.objects.create(
                    application=application,
                    file_name=file_name,
                    object_path=object_path,
                    content_type=content_type,
                    file_size=uploaded.size,
                    uploaded_by=request.user,
                )
        except SupabaseStorageError:
            logger.exception(
                "Application attachment upload failed for application %s.",
                application.pk,
            )
            self._remove_failed_application(application, object_paths)
            return Response(
                {"detail": "Attachments could not be uploaded. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DatabaseError:
            self._remove_failed_application(application, object_paths)
            raise

        application = self._application_queryset().get(pk=application.pk)
        return Response(
            OpportunityApplicationSerializer(
                application, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _remove_failed_application(application, object_paths):
        application.delete()
        for object_path in object_paths:
            try:
                delete_private_file("application_attachments", object_path)
            except SupabaseStorageError:
                logger.exception(
                    "Failed to clean up application attachment %s.", object_path
                )

    @staticmethod
    def _application_queryset():
        return OpportunityApplication.objects.select_related(
            "opportunity__category", "portfolio"
        ).prefetch_related("opportunity__required_skills", "attachments")


class MyOpportunityApplicationsView(generics.ListAPIView):
    permission_classes = [IsActiveStudent]
    serializer_class = OpportunityApplicationSerializer

    def get_queryset(self):
        return OpportunityApplication.objects.filter(
            student=self.request.user
        ).select_related(
            "opportunity__category", "portfolio"
        ).prefetch_related("opportunity__required_skills", "attachments")


class OpportunityApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = OpportunityApplicationSerializer

    def get_queryset(self):
        queryset = OpportunityApplication.objects.select_related(
            "student", "opportunity__category", "portfolio"
        ).prefetch_related("opportunity__required_skills", "attachments")
        if is_opportunity_manager(self.request.user):
            if self.request.user.role == User.Role.ADMINISTRATOR:
                return queryset
            organization = self.request.user.employer_profile.organization_name
            return queryset.filter(opportunity__organization__iexact=organization)
        return queryset.filter(student=self.request.user)

    def get_serializer_class(self):
        if is_opportunity_manager(self.request.user):
            return ManagerOpportunityApplicationSerializer
        return OpportunityApplicationSerializer


class OpportunityManagerApplicationListView(generics.ListAPIView):
    permission_classes = [IsOpportunityManager]
    serializer_class = ManagerOpportunityApplicationSerializer

    def get_queryset(self):
        queryset = OpportunityApplication.objects.select_related(
            "student", "opportunity__category", "portfolio"
        ).prefetch_related("opportunity__required_skills", "attachments")
        if self.request.user.role != User.Role.ADMINISTRATOR:
            organization = self.request.user.employer_profile.organization_name
            queryset = queryset.filter(
                opportunity__organization__iexact=organization
            )
        opportunity_id = self.request.query_params.get("opportunity")
        if opportunity_id:
            queryset = queryset.filter(opportunity_id=opportunity_id)
        application_status = self.request.query_params.get("status")
        if application_status:
            queryset = queryset.filter(status=application_status)
        return queryset


class OpportunityApplicationStatusView(APIView):
    permission_classes = [IsOpportunityManager]

    def patch(self, request, pk):
        queryset = OpportunityApplication.objects.select_for_update().select_related(
            "opportunity"
        )
        if request.user.role != User.Role.ADMINISTRATOR:
            organization = request.user.employer_profile.organization_name
            queryset = queryset.filter(
                opportunity__organization__iexact=organization
            )
        with transaction.atomic():
            application = get_object_or_404(queryset, pk=pk)
            serializer = OpportunityApplicationStatusSerializer(
                application, data=request.data
            )
            serializer.is_valid(raise_exception=True)
            previous_status = application.status
            application.status = serializer.validated_data["status"]
            application.review_note = serializer.validated_data.get(
                "review_note", application.review_note
            )
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save(
                update_fields=(
                    "status",
                    "review_note",
                    "reviewed_by",
                    "reviewed_at",
                    "updated_at",
                )
            )
        if application.status != previous_status:
            create_notification(
                application.student,
                title="Application status updated",
                message=(
                    f"Your application for {application.opportunity.title} is now "
                    f"{application.get_status_display()}."
                ),
                notification_type="application_status",
                related_resource=application,
                target_url="/opportunities/my-applications/",
            )
        application = OpportunityApplication.objects.select_related(
            "student", "opportunity__category", "portfolio"
        ).prefetch_related("opportunity__required_skills", "attachments").get(
            pk=application.pk
        )
        return Response(
            ManagerOpportunityApplicationSerializer(
                application, context={"request": request}
            ).data
        )
