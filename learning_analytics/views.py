from datetime import datetime, time, timedelta

from django.db.models import Count, F, Max, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdministrator
from certificates.models import Certificate
from courses.models import CourseEnrollment, LessonProgress
from courses.permissions import IsActiveStudent, IsCourseStaff
from courses.views import _manageable_courses
from opportunities.models import Opportunity, OpportunityApplication
from opportunities.permissions import IsOpportunityManager
from pathways.models import PathwayStepProgress, Skill, StudentPathwayEnrollment
from pathways.permissions import IsPathwayStaff
from pathways.views import _manageable_pathways
from portfolios.models import PortfolioProject


def _activity_dates(queryset, timestamp_field, start_at=None):
    queryset = queryset.exclude(**{f"{timestamp_field}__isnull": True})
    if start_at is not None:
        queryset = queryset.filter(**{f"{timestamp_field}__gte": start_at})
    return set(
        queryset.annotate(activity_day=TruncDate(timestamp_field))
        .values_list("activity_day", flat=True)
        .distinct()
    )


def _streak_summary(user):
    dates = _activity_dates(
        LessonProgress.objects.filter(enrollment__student=user), "last_accessed_at"
    )
    dates.update(
        _activity_dates(
            PathwayStepProgress.objects.filter(enrollment__student=user),
            "last_accessed_at",
        )
    )
    if not dates:
        return {"current": 0, "longest": 0}

    today = timezone.localdate()
    cursor = today if today in dates else today - timedelta(days=1)
    current = 0
    while cursor in dates:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    previous = None
    for activity_day in sorted(dates):
        run = run + 1 if previous and activity_day == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = activity_day
    return {"current": current, "longest": longest}


def _skills_acquired(user):
    return list(
        Skill.objects.filter(
            required_by_pathways__enrollments__student=user,
            required_by_pathways__enrollments__status=StudentPathwayEnrollment.Status.COMPLETED,
        )
        .values("id", "name", category_name=F("category__name"))
        .distinct()
    )


def _student_dashboard(user):
    enrollments = CourseEnrollment.objects.filter(student=user)
    pathways = StudentPathwayEnrollment.objects.filter(student=user)
    return {
        "enrolled_courses": enrollments.count(),
        "completed_courses": enrollments.filter(
            status=CourseEnrollment.Status.COMPLETED
        ).count(),
        "certificates_earned": Certificate.objects.filter(
            student=user, is_revoked=False
        ).count(),
        "projects_submitted": None,
        "approved_projects": None,
        "project_tracking_available": False,
        "showcased_projects": PortfolioProject.objects.filter(
            portfolio__student=user
        ).count(),
        "active_skill_pathways": pathways.filter(
            status=StudentPathwayEnrollment.Status.IN_PROGRESS
        ).count(),
        "completed_skill_pathways": pathways.filter(
            status=StudentPathwayEnrollment.Status.COMPLETED
        ).count(),
        "pathway_progress": _pathway_progress(user),
        "skills_acquired": _skills_acquired(user),
        "learning_streak": _streak_summary(user),
    }


def _pathway_progress(user):
    enrollments = (
        StudentPathwayEnrollment.objects.filter(student=user)
        .select_related("pathway")
        .annotate(
            total_steps=Count("pathway__steps", distinct=True),
            completed_steps=Count(
                "step_progress",
                filter=Q(step_progress__is_completed=True),
                distinct=True,
            ),
        )
    )
    results = []
    for enrollment in enrollments:
        total = enrollment.total_steps
        completed = enrollment.completed_steps
        results.append(
            {
                "pathway_id": enrollment.pathway_id,
                "name": enrollment.pathway.name,
                "status": enrollment.status,
                "completed_steps": completed,
                "total_steps": total,
                "progress_percentage": round(completed * 100 / total)
                if total
                else 0,
            }
        )
    return results


class StudentDashboardAnalyticsView(APIView):
    permission_classes = [IsActiveStudent]

    def get(self, request):
        return Response(_student_dashboard(request.user))


class StudentProgressAnalyticsView(APIView):
    permission_classes = [IsActiveStudent]

    def get(self, request):
        courses = (
            CourseEnrollment.objects.filter(student=request.user)
            .select_related("course")
            .annotate(
                total_lessons=Count("course__modules__lessons", distinct=True),
                completed_lessons=Count(
                    "lesson_progress",
                    filter=Q(lesson_progress__is_completed=True),
                    distinct=True,
                ),
            )
        )
        course_progress = []
        for enrollment in courses:
            total = enrollment.total_lessons
            completed = enrollment.completed_lessons
            course_progress.append(
                {
                    "course_id": enrollment.course_id,
                    "title": enrollment.course.title,
                    "status": enrollment.status,
                    "enrolled_at": enrollment.enrolled_at,
                    "completed_at": enrollment.completed_at,
                    "completed_lessons": completed,
                    "total_lessons": total,
                    "progress_percentage": round(completed * 100 / total)
                    if total
                    else 0,
                }
            )
        return Response(
            {
                "courses": course_progress,
                "pathways": _pathway_progress(request.user),
                "skills_acquired": _skills_acquired(request.user),
            }
        )


class LearningActivityAnalyticsView(APIView):
    permission_classes = [IsActiveStudent]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", "30"))
        except ValueError as exc:
            raise serializers.ValidationError(
                {"days": "Provide a whole number from 1 to 365."}
            ) from exc
        if not 1 <= days <= 365:
            raise serializers.ValidationError(
                {"days": "Provide a whole number from 1 to 365."}
            )

        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=days - 1)
        start_at = timezone.make_aware(datetime.combine(start_date, time.min))
        buckets = {
            start_date + timedelta(days=offset): {
                "lesson_activity": 0,
                "pathway_step_activity": 0,
                "course_enrollments": 0,
                "pathway_enrollments": 0,
            }
            for offset in range(days)
        }

        sources = (
            (
                LessonProgress.objects.filter(enrollment__student=request.user),
                "last_accessed_at",
                "lesson_activity",
            ),
            (
                PathwayStepProgress.objects.filter(enrollment__student=request.user),
                "last_accessed_at",
                "pathway_step_activity",
            ),
            (
                CourseEnrollment.objects.filter(student=request.user),
                "enrolled_at",
                "course_enrollments",
            ),
            (
                StudentPathwayEnrollment.objects.filter(student=request.user),
                "enrolled_at",
                "pathway_enrollments",
            ),
        )
        for queryset, timestamp_field, result_key in sources:
            rows = (
                queryset.filter(**{f"{timestamp_field}__gte": start_at})
                .annotate(activity_day=TruncDate(timestamp_field))
                .values("activity_day")
                .annotate(count=Count("pk"))
            )
            for row in rows:
                if row["activity_day"] in buckets:
                    buckets[row["activity_day"]][result_key] = row["count"]

        activity = [
            {"date": activity_day.isoformat(), **counts, "total": sum(counts.values())}
            for activity_day, counts in sorted(buckets.items())
        ]
        return Response(
            {
                "period_days": days,
                "start_date": start_date,
                "end_date": end_date,
                "activity": activity,
                "total_activity": sum(item["total"] for item in activity),
                "learning_streak": _streak_summary(request.user),
            }
        )


class CourseAnalyticsView(APIView):
    permission_classes = [IsCourseStaff]

    def get(self, request, course_id):
        course = get_object_or_404(_manageable_courses(request.user), pk=course_id)
        enrollments = (
            CourseEnrollment.objects.filter(course=course)
            .select_related("student")
            .annotate(
                total_lessons=Count("course__modules__lessons", distinct=True),
                completed_lessons=Count(
                    "lesson_progress",
                    filter=Q(lesson_progress__is_completed=True),
                    distinct=True,
                ),
                last_learning_activity=Max("lesson_progress__last_accessed_at"),
            )
        )
        total_enrollments = enrollments.count()
        completed_enrollments = enrollments.filter(
            status=CourseEnrollment.Status.COMPLETED
        ).count()
        student_activity = []
        for enrollment in enrollments:
            student_activity.append(
                {
                    "student_id": str(enrollment.student_id),
                    "student_name": enrollment.student.get_full_name(),
                    "status": enrollment.status,
                    "completed_lessons": enrollment.completed_lessons,
                    "total_lessons": enrollment.total_lessons,
                    "last_activity_at": enrollment.last_learning_activity,
                }
            )
        return Response(
            {
                "course_id": course.pk,
                "course_title": course.title,
                "enrollments": total_enrollments,
                "completed_enrollments": completed_enrollments,
                "completion_rate": round(
                    completed_enrollments * 100 / total_enrollments
                )
                if total_enrollments
                else 0,
                "student_activity": student_activity,
                "project_submissions_available": False,
            }
        )


class PathwayAnalyticsView(APIView):
    permission_classes = [IsPathwayStaff]

    def get(self, request, pathway_id):
        pathway = get_object_or_404(
            _manageable_pathways(request.user), pk=pathway_id
        )
        enrollments = (
            StudentPathwayEnrollment.objects.filter(pathway=pathway)
            .select_related("student")
            .annotate(
                total_steps=Count("pathway__steps", distinct=True),
                completed_steps=Count(
                    "step_progress",
                    filter=Q(step_progress__is_completed=True),
                    distinct=True,
                ),
                last_learning_activity=Max("step_progress__last_accessed_at"),
            )
        )
        return Response(
            {
                "pathway_id": pathway.pk,
                "pathway_name": pathway.name,
                "enrollments": enrollments.count(),
                "completed_enrollments": enrollments.filter(
                    status=StudentPathwayEnrollment.Status.COMPLETED
                ).count(),
                "student_activity": [
                    {
                        "student_id": str(enrollment.student_id),
                        "student_name": enrollment.student.get_full_name(),
                        "status": enrollment.status,
                        "completed_steps": enrollment.completed_steps,
                        "total_steps": enrollment.total_steps,
                        "last_activity_at": enrollment.last_learning_activity,
                    }
                    for enrollment in enrollments
                ],
            }
        )


class OpportunityAnalyticsView(APIView):
    permission_classes = [IsOpportunityManager]

    def get(self, request, opportunity_id):
        queryset = Opportunity.objects.all()
        if request.user.role != User.Role.ADMINISTRATOR:
            organization = request.user.employer_profile.organization_name
            queryset = queryset.filter(organization__iexact=organization)
        opportunity = get_object_or_404(queryset, pk=opportunity_id)
        applications = OpportunityApplication.objects.filter(
            opportunity=opportunity
        )
        counts = {
            item["status"]: item["count"]
            for item in applications.values("status").annotate(count=Count("id"))
        }
        return Response(
            {
                "opportunity_id": opportunity.pk,
                "title": opportunity.title,
                "applications": applications.count(),
                "applications_by_status": counts,
            }
        )


class AdministratorAnalyticsView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        course_enrollments = CourseEnrollment.objects.all()
        pathway_enrollments = StudentPathwayEnrollment.objects.all()
        applications = OpportunityApplication.objects.all()
        return Response(
            {
                "course_enrollments": course_enrollments.count(),
                "completed_courses": course_enrollments.filter(
                    status=CourseEnrollment.Status.COMPLETED
                ).count(),
                "pathway_enrollments": pathway_enrollments.count(),
                "completed_pathways": pathway_enrollments.filter(
                    status=StudentPathwayEnrollment.Status.COMPLETED
                ).count(),
                "opportunity_applications": applications.count(),
                "applications_by_status": {
                    item["status"]: item["count"]
                    for item in applications.values("status").annotate(
                        count=Count("id")
                    )
                },
                "portfolio_projects_showcased": PortfolioProject.objects.count(),
                "project_submissions_available": False,
            }
        )
