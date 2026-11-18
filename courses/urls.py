from django.urls import path

from courses.views import (
    CompleteLessonView,
    CourseCategoryListCreateView,
    CourseDetailView,
    CourseEnrollmentView,
    CourseListView,
    CourseModulesView,
    CourseReviewListCreateView,
    LessonDetailView,
    ManageCourseDetailView,
    ManageCourseListCreateView,
    ManageCourseModulesView,
    ManageCourseStatisticsView,
    ManageCourseThumbnailView,
    ManageLessonDetailView,
    ManageLessonResourceUploadView,
    ManageModuleDetailView,
    ManageModuleLessonsView,
    MyCoursesView,
)

urlpatterns = [
    path("courses/categories/", CourseCategoryListCreateView.as_view(), name="course-categories"),
    path("courses/my-courses/", MyCoursesView.as_view(), name="my-courses"),
    path("courses/manage/", ManageCourseListCreateView.as_view(), name="manage-courses"),
    path(
        "courses/manage/<int:course_id>/",
        ManageCourseDetailView.as_view(),
        name="manage-course-detail",
    ),
    path(
        "courses/manage/<int:course_id>/modules/",
        ManageCourseModulesView.as_view(),
        name="manage-course-modules",
    ),
    path(
        "courses/manage/modules/<int:pk>/",
        ManageModuleDetailView.as_view(),
        name="manage-module-detail",
    ),
    path(
        "courses/manage/modules/<int:module_id>/lessons/",
        ManageModuleLessonsView.as_view(),
        name="manage-module-lessons",
    ),
    path(
        "courses/manage/lessons/<int:pk>/",
        ManageLessonDetailView.as_view(),
        name="manage-lesson-detail",
    ),
    path(
        "courses/manage/lessons/<int:lesson_id>/resources/",
        ManageLessonResourceUploadView.as_view(),
        name="manage-lesson-resources",
    ),
    path(
        "courses/manage/<int:course_id>/thumbnail/",
        ManageCourseThumbnailView.as_view(),
        name="manage-course-thumbnail",
    ),
    path(
        "courses/manage/<int:course_id>/statistics/",
        ManageCourseStatisticsView.as_view(),
        name="manage-course-statistics",
    ),
    path("courses/", CourseListView.as_view(), name="course-list"),
    path(
        "courses/<int:course_id>/enroll/",
        CourseEnrollmentView.as_view(),
        name="course-enroll",
    ),
    path(
        "courses/<int:course_id>/modules/",
        CourseModulesView.as_view(),
        name="course-modules",
    ),
    path(
        "courses/<int:course_id>/reviews/",
        CourseReviewListCreateView.as_view(),
        name="course-review-list",
    ),
    path(
        "lessons/<int:pk>/complete/",
        CompleteLessonView.as_view(),
        name="lesson-complete",
    ),
    path("lessons/<int:pk>/", LessonDetailView.as_view(), name="lesson-detail"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="course-detail"),
]
