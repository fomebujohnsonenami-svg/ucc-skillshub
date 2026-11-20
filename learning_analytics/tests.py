from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from certificates.models import Certificate
from courses.models import (
    Course,
    CourseCategory,
    CourseEnrollment,
    CourseModule,
    Lesson,
    LessonProgress,
)
from pathways.models import (
    PathwayStep,
    PathwayStepProgress,
    Skill,
    SkillCategory,
    SkillPathway,
    StudentPathwayEnrollment,
)


class StudentAnalyticsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student@example.edu",
            password="SecurePassword!2026",
            username="student",
            first_name="Ama",
            last_name="Mensah",
            student_email="student@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.other_student = User.objects.create_user(
            email="other@example.edu",
            password="SecurePassword!2026",
            username="other",
            first_name="Kofi",
            last_name="Asare",
            student_email="other@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.lecturer = User.objects.create_user(
            email="lecturer@example.edu",
            password="SecurePassword!2026",
            username="lecturer",
            first_name="Esi",
            last_name="Owusu",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )

        course_category = CourseCategory.objects.create(name="Digital Skills")
        self.course = Course.objects.create(
            title="Data Foundations",
            description="A data course.",
            category=course_category,
            created_by=self.lecturer,
            estimated_duration_minutes=90,
            status=Course.Status.PUBLISHED,
        )
        module = CourseModule.objects.create(course=self.course, title="Basics")
        self.lesson = Lesson.objects.create(module=module, title="First lesson")
        self.course_enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
            status=CourseEnrollment.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        LessonProgress.objects.create(
            enrollment=self.course_enrollment,
            lesson=self.lesson,
            is_completed=True,
            completed_at=timezone.now(),
        )
        Certificate.objects.create(student=self.student, course=self.course)

        self.pathway_category = SkillCategory.objects.create(name="Technology")
        self.skill = Skill.objects.create(
            category=self.pathway_category, name="Data analysis"
        )
        self.pathway = SkillPathway.objects.create(
            name="Data Analyst",
            description="A data pathway.",
            category=self.pathway_category,
            created_by=self.lecturer,
            estimated_duration_weeks=4,
            status=SkillPathway.Status.PUBLISHED,
        )
        self.pathway.required_skills.add(self.skill)
        step = PathwayStep.objects.create(
            pathway=self.pathway, title="Analyze a dataset", order=1
        )
        self.pathway_enrollment = StudentPathwayEnrollment.objects.create(
            pathway=self.pathway,
            student=self.student,
            status=StudentPathwayEnrollment.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        PathwayStepProgress.objects.create(
            enrollment=self.pathway_enrollment,
            step=step,
            is_completed=True,
            completed_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.student)

    def test_student_dashboard_and_progress_use_only_authenticated_records(self):
        dashboard = self.client.get("/api/v1/analytics/student-dashboard/")
        progress = self.client.get("/api/v1/analytics/student-progress/")

        self.assertEqual(dashboard.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard.data["enrolled_courses"], 1)
        self.assertEqual(dashboard.data["completed_courses"], 1)
        self.assertEqual(dashboard.data["certificates_earned"], 1)
        self.assertEqual(dashboard.data["completed_skill_pathways"], 1)
        self.assertEqual(dashboard.data["skills_acquired"][0]["name"], "Data analysis")
        self.assertIsNone(dashboard.data["projects_submitted"])
        self.assertFalse(dashboard.data["project_tracking_available"])
        self.assertEqual(len(progress.data["courses"]), 1)
        self.assertEqual(progress.data["courses"][0]["progress_percentage"], 100)

        self.client.force_authenticate(user=self.other_student)
        other_dashboard = self.client.get("/api/v1/analytics/student-dashboard/")
        self.assertEqual(other_dashboard.status_code, status.HTTP_200_OK)
        self.assertEqual(other_dashboard.data["enrolled_courses"], 0)
        self.assertEqual(other_dashboard.data["certificates_earned"], 0)
        self.assertEqual(other_dashboard.data["pathway_progress"], [])

    def test_learning_activity_aggregates_real_records_and_validates_period(self):
        response = self.client.get("/api/v1/analytics/learning-activity/?days=3")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["period_days"], 3)
        self.assertEqual(response.data["total_activity"], 4)
        self.assertEqual(response.data["learning_streak"]["current"], 1)

        invalid = self.client.get("/api/v1/analytics/learning-activity/?days=0")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_course_and_pathway_analytics_are_manager_scoped(self):
        self.client.force_authenticate(user=self.lecturer)
        course_analytics = self.client.get(
            f"/api/v1/analytics/courses/{self.course.pk}/"
        )
        pathway_analytics = self.client.get(
            f"/api/v1/analytics/pathways/{self.pathway.pk}/"
        )
        self.assertEqual(course_analytics.status_code, status.HTTP_200_OK)
        self.assertEqual(course_analytics.data["enrollments"], 1)
        self.assertEqual(course_analytics.data["completed_enrollments"], 1)
        self.assertFalse(course_analytics.data["project_submissions_available"])
        self.assertEqual(pathway_analytics.status_code, status.HTTP_200_OK)
        self.assertEqual(pathway_analytics.data["enrollments"], 1)

        other_lecturer = User.objects.create_user(
            email="other-lecturer@example.edu",
            password="SecurePassword!2026",
            username="other-lecturer",
            first_name="Kojo",
            last_name="Boateng",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=other_lecturer)
        self.assertEqual(
            self.client.get(
                f"/api/v1/analytics/courses/{self.course.pk}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/analytics/pathways/{self.pathway.pk}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
