from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.permissions import IsActiveStudent
from portfolios.models import (
    PortfolioCertificate,
    PortfolioProject,
    PortfolioSkill,
    PortfolioSocialLink,
    StudentPortfolio,
)
from portfolios.serializers import (
    PortfolioCertificateSerializer,
    PortfolioProjectSerializer,
    PortfolioSkillSerializer,
    PortfolioSocialLinkSerializer,
    PublicPortfolioSerializer,
    StudentPortfolioSerializer,
)


def _student_portfolio(request):
    portfolio = getattr(request, "_student_portfolio", None)
    if portfolio is None:
        portfolio, _ = StudentPortfolio.objects.get_or_create(student=request.user)
        request._student_portfolio = portfolio
        request.user.portfolio = portfolio
    return portfolio


class StudentPortfolioView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentPortfolioSerializer
    permission_classes = [IsActiveStudent]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return _student_portfolio(self.request)


class PortfolioSkillListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioSkillSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioSkill.objects.filter(portfolio=_student_portfolio(self.request))

    def perform_create(self, serializer):
        serializer.save(portfolio=_student_portfolio(self.request))


class PortfolioSkillDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioSkillSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioSkill.objects.filter(portfolio=_student_portfolio(self.request))


class PortfolioProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioProjectSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioProject.objects.filter(
            portfolio=_student_portfolio(self.request)
        )

    def perform_create(self, serializer):
        serializer.save(portfolio=_student_portfolio(self.request))


class PortfolioProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioProjectSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioProject.objects.filter(
            portfolio=_student_portfolio(self.request)
        )


class PortfolioCertificateListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioCertificateSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return (
            PortfolioCertificate.objects.filter(
                portfolio=_student_portfolio(self.request),
                certificate__is_revoked=False,
            )
            .select_related("certificate__course", "certificate__pathway")
        )

    def perform_create(self, serializer):
        serializer.save(portfolio=_student_portfolio(self.request))


class PortfolioCertificateDeleteView(generics.DestroyAPIView):
    serializer_class = PortfolioCertificateSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioCertificate.objects.filter(
            portfolio=_student_portfolio(self.request)
        )


class PortfolioSocialLinkListCreateView(generics.ListCreateAPIView):
    serializer_class = PortfolioSocialLinkSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioSocialLink.objects.filter(
            portfolio=_student_portfolio(self.request)
        )

    def perform_create(self, serializer):
        serializer.save(portfolio=_student_portfolio(self.request))


class PortfolioSocialLinkDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioSocialLinkSerializer
    permission_classes = [IsActiveStudent]

    def get_queryset(self):
        return PortfolioSocialLink.objects.filter(
            portfolio=_student_portfolio(self.request)
        )


class PublicPortfolioView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_object_or_404(
            StudentPortfolio.objects.filter(is_public=True)
            .select_related("student")
            .prefetch_related("skills", "social_links"),
            slug=slug,
        )
        return Response(
            PublicPortfolioSerializer(
                portfolio, context={"request": request}
            ).data
        )
