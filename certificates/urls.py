from django.urls import path

from certificates.views import (
    AchievementListView,
    CertificateDetailView,
    CertificateDownloadView,
    CertificateListView,
    CertificateVerificationView,
    MyAchievementsView,
)


urlpatterns = [
    path("certificates/", CertificateListView.as_view(), name="certificate-list"),
    path(
        "certificates/verify/<str:token>/",
        CertificateVerificationView.as_view(),
        name="certificate-verify",
    ),
    path(
        "certificates/<int:pk>/download/",
        CertificateDownloadView.as_view(),
        name="certificate-download",
    ),
    path(
        "certificates/<int:pk>/",
        CertificateDetailView.as_view(),
        name="certificate-detail",
    ),
    path("achievements/", AchievementListView.as_view(), name="achievement-list"),
    path(
        "achievements/my-achievements/",
        MyAchievementsView.as_view(),
        name="my-achievements",
    ),
]
