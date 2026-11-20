import tempfile
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from certificates.models import Achievement, Certificate, StudentAchievement
from certificates.services import award_achievements, issue_course_certificate
from notifications.models import Notification
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
    SkillCategory,
    SkillPathway,
    StudentPathwayEnrollment,
)


class CertificateAndAchievementTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.enterContext(override_settings(MEDIA_ROOT=self.media.name))
        self.addCleanup(self.media.cleanup)
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student@example.edu",
            password="SecurePassword!2026",
            username="student",
            first_name="Kojo",
            last_name="Mensah",
            student_email="student@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.other_student = User.objects.create_user(
            email="other@example.edu",
            password="SecurePassword!2026",
            username="other",
            first_name="Abena",
            last_name="Boateng",
            student_email="other@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.category = CourseCategory.objects.create(name="Digital Skills")
        self.course = Course.objects.create(
            title="Data Foundations",
            description="Learn data skills.",
            category=self.category,
            created_by=self.student,
            estimated_duration_minutes=60,
            status=Course.Status.PUBLISHED,
            certificate_eligible=True,
        )
        module = CourseModule.objects.create(course=self.course, title="Basics")
        self.lesson = Lesson.objects.create(
            module=module, title="First lesson", content="Learn the basics."
        )
        self.enrollment = CourseEnrollment.objects.create(
            course=self.course, student=self.student
        )
        self.pathway_category = SkillCategory.objects.create(name="Technology")
        self.pathway = SkillPathway.objects.create(
            name="Data Analyst",
            description="A data pathway.",
            category=self.pathway_category,
            created_by=self.student,
            estimated_duration_weeks=4,
            status=SkillPathway.Status.PUBLISHED,
        )
        self.pathway_step = PathwayStep.objects.create(
            pathway=self.pathway, title="Foundations", order=1
        )
        self.pathway_enrollment = StudentPathwayEnrollment.objects.create(
            pathway=self.pathway, student=self.student
        )
        self.client.force_authenticate(user=self.student)

    def test_incomplete_or_ineligible_course_cannot_receive_certificate(self):
        self.assertIsNone(issue_course_certificate(self.enrollment))
        self.course.certificate_eligible = False
        self.course.save(update_fields=["certificate_eligible"])

        response = self.client.post(f"/api/v1/lessons/{self.lesson.pk}/complete/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Certificate.objects.filter(course=self.course).exists())

    def test_course_completion_issues_one_pdf_and_duplicate_completion_is_idempotent(self):
        url = f"/api/v1/lessons/{self.lesson.pk}/complete/"
        completed = self.client.post(url)
        first_completed_at = LessonProgress.objects.get(
            enrollment=self.enrollment
        ).completed_at
        repeated = self.client.post(url)

        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        progress = LessonProgress.objects.get(enrollment=self.enrollment)
        self.assertEqual(progress.completed_at, first_completed_at)
        certificate = Certificate.objects.get(student=self.student, course=self.course)
        self.assertTrue(certificate.certificate_file.name.endswith(".pdf"))
        with certificate.certificate_file.open("rb") as pdf:
            self.assertTrue(pdf.read().startswith(b"%PDF-"))
        self.assertEqual(Certificate.objects.filter(course=self.course).count(), 1)
        self.assertEqual(
            StudentAchievement.objects.filter(
                student=self.student,
                achievement__key="first-course-completed",
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.Type.CERTIFICATE_ISSUED,
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.Type.LEARNING_PROGRESS,
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.Type.ACHIEVEMENT_AWARDED,
            ).count(),
            1,
        )

    def test_download_is_student_scoped_and_verification_is_public_and_minimal(self):
        self.client.post(f"/api/v1/lessons/{self.lesson.pk}/complete/")
        certificate = Certificate.objects.get(student=self.student, course=self.course)

        download = self.client.get(
            f"/api/v1/certificates/{certificate.pk}/download/"
        )
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertEqual(download["Content-Type"], "application/pdf")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertTrue(b"".join(download.streaming_content).startswith(b"%PDF-"))
        download.close()

        self.client.force_authenticate(user=self.other_student)
        private_detail = self.client.get(f"/api/v1/certificates/{certificate.pk}/")
        private_download = self.client.get(
            f"/api/v1/certificates/{certificate.pk}/download/"
        )
        self.assertEqual(private_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(private_download.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=None)
        verification = self.client.get(
            f"/api/v1/certificates/verify/{certificate.verification_token}/"
        )
        verification_page = self.client.get(
            f"/certificates/verify/{certificate.verification_token}/"
        )
        self.assertEqual(verification.status_code, status.HTTP_200_OK)
        self.assertTrue(verification.data["valid"])
        self.assertEqual(verification.data["recipient"], "Kojo M.")
        self.assertNotIn("email", verification.data)
        self.assertNotIn("student", verification.data)
        self.assertGreaterEqual(len(certificate.verification_token), 40)
        self.assertEqual(verification_page.status_code, status.HTTP_200_OK)
        self.assertContains(verification_page, "Valid certificate")
        self.assertNotContains(verification_page, "student@example.edu")

    def test_pathway_certificate_requires_and_follows_completed_steps(self):
        self.assertFalse(
            Certificate.objects.filter(student=self.student, pathway=self.pathway).exists()
        )
        response = self.client.post(
            f"/api/v1/pathway-steps/{self.pathway_step.pk}/complete/"
        )
        repeated = self.client.post(
            f"/api/v1/pathway-steps/{self.pathway_step.pk}/complete/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        certificate = Certificate.objects.get(
            student=self.student, pathway=self.pathway
        )
        self.assertEqual(certificate.completion_info["completed_steps"], 1)
        self.assertEqual(certificate.completion_info["total_steps"], 1)
        self.assertEqual(
            StudentAchievement.objects.filter(
                student=self.student,
                achievement__key="skill-pathway-completed",
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.Type.PATHWAY_MILESTONE,
            ).count(),
            1,
        )

    def test_achievement_awards_are_automatic_and_duplicate_safe(self):
        self.client.post(f"/api/v1/lessons/{self.lesson.pk}/complete/")
        awards = award_achievements(self.student, event="course_completed")
        award_achievements(self.student, event="course_completed")

        self.assertEqual(
            StudentAchievement.objects.filter(
                student=self.student,
                achievement__key="first-course-completed",
            ).count(),
            1,
        )
        self.assertEqual(Achievement.objects.filter(is_active=True).count(), 6)
        self.assertEqual(awards, [])

    def test_seven_consecutive_learning_days_award_streak_achievement(self):
        today = timezone.localdate()
        for days_ago in range(7):
            lesson = Lesson.objects.create(
                module=self.lesson.module,
                title=f"Streak lesson {days_ago}",
                content="Learning activity.",
                order=days_ago + 1,
            )
            completed_date = today - timedelta(days=days_ago)
            completed_at = timezone.make_aware(
                datetime.combine(completed_date, datetime.min.time())
                + timedelta(hours=12)
            )
            LessonProgress.objects.create(
                enrollment=self.enrollment,
                lesson=lesson,
                is_completed=True,
                completed_at=completed_at,
            )

        award_achievements(self.student, event="lesson_completed")

        self.assertTrue(
            StudentAchievement.objects.filter(
                student=self.student,
                achievement__key="seven-day-learning-streak",
            ).exists()
        )

    def test_project_approval_event_awards_project_achievement_once(self):
        awards = award_achievements(self.student, event="project_approved")
        repeated = award_achievements(self.student, event="project_approved")

        self.assertEqual(len(awards), 1)
        self.assertEqual(repeated, [])
        self.assertEqual(
            StudentAchievement.objects.filter(
                student=self.student,
                achievement__key="first-project-approved",
            ).count(),
            1,
        )

    def test_certificate_list_and_details_are_read_only(self):
        self.client.post(f"/api/v1/lessons/{self.lesson.pk}/complete/")
        certificate = Certificate.objects.get(student=self.student, course=self.course)

        listing = self.client.get("/api/v1/certificates/")
        detail = self.client.get(f"/api/v1/certificates/{certificate.pk}/")
        create = self.client.post("/api/v1/certificates/", {}, format="json")

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["certificate_id"], certificate.certificate_id)
        self.assertEqual(create.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
