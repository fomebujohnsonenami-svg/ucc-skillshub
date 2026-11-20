from django.urls import path

from portfolios.views import (
    PortfolioCertificateDeleteView,
    PortfolioCertificateListCreateView,
    PortfolioProjectDetailView,
    PortfolioProjectListCreateView,
    PortfolioSkillDetailView,
    PortfolioSkillListCreateView,
    PortfolioSocialLinkDetailView,
    PortfolioSocialLinkListCreateView,
    PublicPortfolioView,
    StudentPortfolioView,
)


urlpatterns = [
    path("portfolio/me/", StudentPortfolioView.as_view(), name="student-portfolio"),
    path(
        "portfolio/public/<slug:slug>/",
        PublicPortfolioView.as_view(),
        name="public-portfolio",
    ),
    path(
        "portfolio/projects/",
        PortfolioProjectListCreateView.as_view(),
        name="portfolio-project-list",
    ),
    path(
        "portfolio/projects/<int:pk>/",
        PortfolioProjectDetailView.as_view(),
        name="portfolio-project-detail",
    ),
    path(
        "portfolio/skills/",
        PortfolioSkillListCreateView.as_view(),
        name="portfolio-skill-list",
    ),
    path(
        "portfolio/skills/<int:pk>/",
        PortfolioSkillDetailView.as_view(),
        name="portfolio-skill-detail",
    ),
    path(
        "portfolio/certificates/",
        PortfolioCertificateListCreateView.as_view(),
        name="portfolio-certificate-list",
    ),
    path(
        "portfolio/certificates/<int:pk>/",
        PortfolioCertificateDeleteView.as_view(),
        name="portfolio-certificate-delete",
    ),
    path(
        "portfolio/social-links/",
        PortfolioSocialLinkListCreateView.as_view(),
        name="portfolio-social-link-list",
    ),
    path(
        "portfolio/social-links/<int:pk>/",
        PortfolioSocialLinkDetailView.as_view(),
        name="portfolio-social-link-detail",
    ),
]
