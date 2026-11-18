from django.urls import path

from pathways.views import (
    CompletePathwayStepView,
    ManagePathwayDetailView,
    ManagePathwayListCreateView,
    ManagePathwayStatisticsView,
    ManagePathwayStepDetailView,
    ManagePathwayStepsView,
    ManagePathwayThumbnailView,
    ManageSkillCategoryListCreateView,
    ManageSkillListCreateView,
    MyPathwaysView,
    PathwayDetailView,
    PathwayEnrollmentView,
    PathwayListView,
    PathwayProgressView,
    ReorderPathwayStepsView,
    SkillCategoryListCreateView,
    SkillListView,
)


urlpatterns = [
    path("pathway-categories/", SkillCategoryListCreateView.as_view(), name="pathway-categories"),
    path("skills/", SkillListView.as_view(), name="skill-list"),
    path("pathways/my-pathways/", MyPathwaysView.as_view(), name="my-pathways"),
    path("pathways/manage/categories/", ManageSkillCategoryListCreateView.as_view(), name="manage-pathway-categories"),
    path("pathways/manage/skills/", ManageSkillListCreateView.as_view(), name="manage-skills"),
    path("pathways/manage/", ManagePathwayListCreateView.as_view(), name="manage-pathways"),
    path(
        "pathways/manage/<int:pathway_id>/",
        ManagePathwayDetailView.as_view(),
        name="manage-pathway-detail",
    ),
    path(
        "pathways/manage/<int:pathway_id>/steps/",
        ManagePathwayStepsView.as_view(),
        name="manage-pathway-steps",
    ),
    path(
        "pathways/manage/<int:pathway_id>/steps/reorder/",
        ReorderPathwayStepsView.as_view(),
        name="reorder-pathway-steps",
    ),
    path(
        "pathways/manage/<int:pathway_id>/thumbnail/",
        ManagePathwayThumbnailView.as_view(),
        name="manage-pathway-thumbnail",
    ),
    path(
        "pathways/manage/<int:pathway_id>/statistics/",
        ManagePathwayStatisticsView.as_view(),
        name="manage-pathway-statistics",
    ),
    path(
        "pathways/manage/steps/<int:pk>/",
        ManagePathwayStepDetailView.as_view(),
        name="manage-pathway-step-detail",
    ),
    path(
        "pathways/<int:pathway_id>/enroll/",
        PathwayEnrollmentView.as_view(),
        name="pathway-enroll",
    ),
    path(
        "pathways/<int:pathway_id>/progress/",
        PathwayProgressView.as_view(),
        name="pathway-progress",
    ),
    path(
        "pathway-steps/<int:pk>/complete/",
        CompletePathwayStepView.as_view(),
        name="pathway-step-complete",
    ),
    path("pathways/", PathwayListView.as_view(), name="pathway-list"),
    path(
        "pathways/<int:pk>/",
        PathwayDetailView.as_view(),
        name="pathway-detail",
    ),
]
