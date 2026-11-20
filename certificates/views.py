from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, permissions
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from certificates.models import Achievement, Certificate, StudentAchievement
from certificates.serializers import (
    AchievementSerializer,
    CertificateSerializer,
    PublicCertificateVerificationSerializer,
    StudentAchievementSerializer,
)
from courses.permissions import IsActiveStudent


class CertificateListView(generics.ListAPIView):
    serializer_class = CertificateSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return Certificate.objects.filter(student=self.request.user).select_related(
            "course", "pathway"
        )


class CertificateDetailView(generics.RetrieveAPIView):
    serializer_class = CertificateSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return Certificate.objects.filter(student=self.request.user).select_related(
            "course", "pathway"
        )


class CertificateDownloadView(APIView):
    permission_classes = [IsActiveStudent]

    def get(self, request, pk):
        certificate = get_object_or_404(
            Certificate.objects.filter(student=request.user), pk=pk
        )
        if not certificate.certificate_file:
            raise APIException("The certificate PDF is not available.")
        return FileResponse(
            certificate.certificate_file.open("rb"),
            as_attachment=True,
            filename=f"{certificate.certificate_id}.pdf",
            content_type="application/pdf",
        )


class CertificateVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        certificate = get_object_or_404(
            Certificate.objects.select_related("course", "pathway", "student"),
            verification_token=token,
        )
        return Response(PublicCertificateVerificationSerializer(certificate).data)


def certificate_verification_page(request, token):
    certificate = get_object_or_404(
        Certificate.objects.select_related("course", "pathway", "student"),
        verification_token=token,
    )
    details = PublicCertificateVerificationSerializer(certificate).data
    return render(
        request,
        "certificates/verify.html",
        {"certificate": details},
    )


class AchievementListView(generics.ListAPIView):
    serializer_class = AchievementSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return Achievement.objects.filter(is_active=True)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        awards = StudentAchievement.objects.filter(student=self.request.user)
        context["award_ids"] = set(awards.values_list("achievement_id", flat=True))
        context["awarded_at"] = {
            award.achievement_id: award.awarded_at for award in awards
        }
        return context


class MyAchievementsView(generics.ListAPIView):
    serializer_class = StudentAchievementSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return (
            StudentAchievement.objects.filter(
                student=self.request.user, achievement__is_active=True
            )
            .select_related("achievement")
            .order_by("-awarded_at", "-id")
        )
