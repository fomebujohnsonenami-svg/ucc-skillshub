from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, UserSettings
from courses.models import Course, CourseCategory
from notifications.models import Notification
from notifications.services import create_notification


class NotificationsApiTests(TestCase):
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
        self.client.force_authenticate(user=self.student)

    def test_notification_list_read_mark_all_and_delete_are_recipient_scoped(self):
        first = Notification.objects.create(
            recipient=self.student,
            title="Course update",
            message="A lesson was completed.",
            notification_type=Notification.Type.LEARNING_PROGRESS,
        )
        second = Notification.objects.create(
            recipient=self.student,
            title="Certificate earned",
            message="A certificate is ready.",
            notification_type=Notification.Type.CERTIFICATE_ISSUED,
        )
        other = Notification.objects.create(
            recipient=self.other_student,
            title="Private",
            message="Only for another student.",
            notification_type=Notification.Type.PLATFORM_ANNOUNCEMENT,
        )

        listing = self.client.get("/api/v1/notifications/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["unread_count"], 2)
        self.assertEqual(len(listing.data["results"]), 2)

        marked = self.client.patch(f"/api/v1/notifications/{first.pk}/read/")
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertTrue(marked.data["is_read"])

        forbidden_read = self.client.patch(
            f"/api/v1/notifications/{other.pk}/read/"
        )
        self.assertEqual(forbidden_read.status_code, status.HTTP_404_NOT_FOUND)

        mark_all = self.client.post("/api/v1/notifications/mark-all-read/")
        self.assertEqual(mark_all.data["updated_count"], 1)
        self.assertEqual(
            self.client.get("/api/v1/notifications/").data["unread_count"], 0
        )

        deleted = self.client.delete(f"/api/v1/notifications/{second.pk}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        forbidden_delete = self.client.delete(
            f"/api/v1/notifications/{other.pk}/"
        )
        self.assertEqual(forbidden_delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_notification_preferences_suppress_disabled_types(self):
        UserSettings.objects.create(
            user=self.student,
            notification_preferences={"new_opportunity": False},
        )

        suppressed = create_notification(
            self.student,
            title="New role",
            message="A new role is available.",
            notification_type="new_opportunity",
        )
        created = create_notification(
            self.student,
            title="Completed",
            message="A lesson was completed.",
            notification_type="learning_progress",
        )

        self.assertIsNone(suppressed)
        self.assertIsNotNone(created)
        self.assertEqual(
            Notification.objects.filter(recipient=self.student).count(), 1
        )

    def test_course_enrollment_creates_one_confirmation_notification(self):
        category = CourseCategory.objects.create(name="Digital Skills")
        course = Course.objects.create(
            title="Learning Foundations",
            description="A course for testing enrollment notifications.",
            category=category,
            created_by=self.student,
            estimated_duration_minutes=60,
            status=Course.Status.PUBLISHED,
        )

        first = self.client.post(f"/api/v1/courses/{course.pk}/enroll/")
        repeated = self.client.post(f"/api/v1/courses/{course.pk}/enroll/")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.Type.ENROLLMENT_CONFIRMATION,
            ).count(),
            1,
        )
