from django.urls import path

from learning_analytics.views import (
    AdministratorAnalyticsView,
    CourseAnalyticsView,
    LearningActivityAnalyticsView,
    OpportunityAnalyticsView,
    PathwayAnalyticsView,
    StudentDashboardAnalyticsView,
    StudentProgressAnalyticsView,
)

urlpatterns = [
    path(
        "analytics/student-dashboard/",
        StudentDashboardAnalyticsView.as_view(),
        name="student-dashboard-analytics",
    ),
    path(
        "analytics/student-progress/",
        StudentProgressAnalyticsView.as_view(),
        name="student-progress-analytics",
    ),
    path(
        "analytics/learning-activity/",
        LearningActivityAnalyticsView.as_view(),
        name="learning-activity-analytics",
    ),
    path(
        "analytics/courses/<int:course_id>/",
        CourseAnalyticsView.as_view(),
        name="course-analytics",
    ),
    path(
        "analytics/pathways/<int:pathway_id>/",
        PathwayAnalyticsView.as_view(),
        name="pathway-analytics",
    ),
    path(
        "analytics/opportunities/<int:opportunity_id>/",
        OpportunityAnalyticsView.as_view(),
        name="opportunity-analytics",
    ),
    path(
        "analytics/administrator/",
        AdministratorAnalyticsView.as_view(),
        name="administrator-analytics",
    ),
]
