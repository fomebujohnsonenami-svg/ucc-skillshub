from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import (
    Course,
    CourseCategory,
    CourseEnrollment,
    CourseModule,
    CourseReview,
    Lesson,
    LessonProgress,
)

PASSWORD = "V3ry$trong-Password-2026!"


class CourseApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = CourseCategory.objects.create(
            name="Digital Skills", slug="digital-skills"
        )
        self.lecturer = User.objects.create_user(
            email="lecturer@example.edu",
            password=PASSWORD,
            username="lecturer",
            first_name="Ama",
            last_name="Owusu",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.student = User.objects.create_user(
            email="student@example.edu",
            password=PASSWORD,
            username="student",
            first_name="Kojo",
            last_name="Mensah",
            student_email="student@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.other_lecturer = User.objects.create_user(
            email="other@example.edu",
            password=PASSWORD,
            username="other",
            first_name="Kofi",
            last_name="Tetteh",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )

    def create_course(self, title="Data Foundations", duration=90, **kwargs):
        self.client.force_authenticate(user=self.lecturer)
        created = self.client.post(
            "/api/v1/courses/manage/",
            {
                "title": title,
                "description": f"Learn practical data skills with {title}.",
                "category": self.category.pk,
                "difficulty": kwargs.pop("difficulty", Course.Difficulty.BEGINNER),
                "estimated_duration_minutes": duration,
                "learning_objectives": ["Analyze data", "Present findings"],
                "prerequisites": [],
                "certificate_eligible": kwargs.pop("certificate_eligible", True),
                **kwargs,
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        course_id = created.data["id"]
        module = self.client.post(
            f"/api/v1/courses/manage/{course_id}/modules/",
            {"title": "Getting started", "description": "First module."},
            format="json",
        )
        self.assertEqual(module.status_code, status.HTTP_201_CREATED, module.data)
        lesson = self.client.post(
            f"/api/v1/courses/manage/modules/{module.data['id']}/lessons/",
            {
                "title": "First lesson",
                "content_type": Lesson.ContentType.TEXT,
                "content": "A first practical lesson.",
                "duration_minutes": 30,
            },
            format="json",
        )
        self.assertEqual(lesson.status_code, status.HTTP_201_CREATED, lesson.data)
        published = self.client.patch(
            f"/api/v1/courses/manage/{course_id}/",
            {"status": Course.Status.PUBLISHED},
            format="json",
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK, published.data)
        return Course.objects.get(pk=course_id), module.data, lesson.data

    def test_staff_can_create_course_curriculum_and_publish(self):
        course, module, lesson = self.create_course()

        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(course.slug)
        self.assertEqual(course.created_by, self.lecturer)
        self.assertEqual(course.course_instructors.get().instructor, self.lecturer)
        self.assertEqual(module["order"], 0)
        self.assertEqual(lesson["order"], 0)

    def test_students_cannot_manage_courses_or_create_categories(self):
        self.client.force_authenticate(user=self.student)

        course_response = self.client.post(
            "/api/v1/courses/manage/",
            {"title": "Not allowed"},
            format="json",
        )
        category_response = self.client.post(
            "/api/v1/courses/categories/",
            {"name": "Blocked", "slug": "blocked"},
            format="json",
        )

        self.assertEqual(course_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(category_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Course.objects.exists())

    def test_lecturers_can_only_manage_courses_they_own(self):
        course, _, _ = self.create_course()
        self.client.force_authenticate(user=self.other_lecturer)

        detail = self.client.get(f"/api/v1/courses/manage/{course.pk}/")
        update = self.client.patch(
            f"/api/v1/courses/manage/{course.pk}/",
            {"title": "Unauthorized edit"},
            format="json",
        )

        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update.status_code, status.HTTP_404_NOT_FOUND)

    def test_course_cannot_publish_without_a_lesson(self):
        self.client.force_authenticate(user=self.lecturer)
        course = self.client.post(
            "/api/v1/courses/manage/",
            {
                "title": "Empty course",
                "description": "A course without lessons.",
                "category": self.category.pk,
                "difficulty": Course.Difficulty.BEGINNER,
                "estimated_duration_minutes": 60,
            },
            format="json",
        )

        published = self.client.patch(
            f"/api/v1/courses/manage/{course.data['id']}/",
            {"status": Course.Status.PUBLISHED},
            format="json",
        )

        self.assertEqual(published.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Course.objects.get(pk=course.data["id"]).status, Course.Status.DRAFT
        )

    def test_catalogue_search_filters_category_level_duration_certificate_and_sort(self):
        short_course, _, _ = self.create_course("Data for Teams", duration=90)
        long_course, _, _ = self.create_course(
            "Advanced Analytics",
            duration=360,
            difficulty=Course.Difficulty.ADVANCED,
            certificate_eligible=False,
        )
        self.client.force_authenticate(user=None)

        response = self.client.get(
            "/api/v1/courses/?search=ANALYTICS&category=digital-skills"
            "&difficulty=advanced&duration=long&certificate=false&sort=duration"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], long_course.pk)
        self.assertNotEqual(short_course.pk, long_course.pk)

    def test_catalogue_paginates_published_courses_and_hides_drafts(self):
        for index in range(13):
            self.create_course(f"Published Course {index}")
        self.client.force_authenticate(user=self.lecturer)
        draft = self.client.post(
            "/api/v1/courses/manage/",
            {
                "title": "Still a draft",
                "description": "Not visible publicly",
                "category": self.category.pk,
                "estimated_duration_minutes": 45,
            },
            format="json",
        )
        self.assertEqual(draft.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=None)

        first_page = self.client.get("/api/v1/courses/?sort=title&page_size=5")
        second_page = self.client.get("/api/v1/courses/?sort=title&page=2")

        self.assertEqual(first_page.data["count"], 13)
        self.assertEqual(len(first_page.data["results"]), 12)
        self.assertIsNotNone(first_page.data["next"])
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertNotIn(
            "Still a draft", [course["title"] for course in first_page.data["results"]]
        )

    def test_enrollment_is_unique_and_my_courses_contains_progress(self):
        course, _, _ = self.create_course()
        self.client.force_authenticate(user=self.student)

        first = self.client.post(f"/api/v1/courses/{course.pk}/enroll/")
        duplicate = self.client.post(f"/api/v1/courses/{course.pk}/enroll/")
        my_courses = self.client.get("/api/v1/courses/my-courses/")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_200_OK)
        self.assertEqual(CourseEnrollment.objects.count(), 1)
        self.assertEqual(my_courses.status_code, status.HTTP_200_OK)
        self.assertEqual(my_courses.data["count"], 1)
        self.assertEqual(
            my_courses.data["results"][0]["course"]["title"], course.title
        )
        self.assertEqual(my_courses.data["results"][0]["progress_percentage"], 0)

    def test_students_cannot_access_nonpreview_lesson_before_enrollment(self):
        _, _, lesson = self.create_course()
        self.client.force_authenticate(user=self.student)

        response = self.client.get(f"/api/v1/lessons/{lesson['id']}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_enrolled_student_can_access_complete_and_resume_lessons(self):
        course, _, first_lesson = self.create_course()
        second_module = CourseModule.objects.create(
            course=course, title="Next module", order=1
        )
        second_lesson = Lesson.objects.create(
            module=second_module,
            title="Second lesson",
            content="Follow-up content.",
            order=0,
        )
        self.client.force_authenticate(user=self.student)
        enrollment = self.client.post(f"/api/v1/courses/{course.pk}/enroll/")
        first_access = self.client.get(f"/api/v1/lessons/{first_lesson['id']}/")
        first_complete = self.client.post(
            f"/api/v1/lessons/{first_lesson['id']}/complete/"
        )
        second_complete = self.client.post(
            f"/api/v1/lessons/{second_lesson.pk}/complete/"
        )
        my_courses = self.client.get("/api/v1/courses/my-courses/")

        self.assertEqual(enrollment.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first_access.status_code, status.HTTP_200_OK)
        self.assertEqual(first_access.data["content"], "A first practical lesson.")
        self.assertEqual(first_complete.data["progress_percentage"], 50)
        self.assertEqual(second_complete.data["progress_percentage"], 100)
        self.assertEqual(
            second_complete.data["status"], CourseEnrollment.Status.COMPLETED
        )
        self.assertEqual(
            my_courses.data["results"][0]["last_accessed_lesson"],
            second_lesson.pk,
        )
        self.assertEqual(
            LessonProgress.objects.filter(
                enrollment__course=course, is_completed=True
            ).count(),
            2,
        )

    def test_preview_lessons_are_accessible_but_restricted_lessons_are_not(self):
        course, _, lesson_data = self.create_course()
        lesson = Lesson.objects.get(pk=lesson_data["id"])
        lesson.is_preview = True
        lesson.save(update_fields=["is_preview"])
        self.client.force_authenticate(user=self.student)

        preview = self.client.get(f"/api/v1/lessons/{lesson.pk}/")
        other_lesson = Lesson.objects.create(
            module=lesson.module,
            title="Restricted",
            content="Private content",
            order=1,
        )
        restricted = self.client.get(f"/api/v1/lessons/{other_lesson.pk}/")

        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(restricted.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(CourseEnrollment.objects.filter(course=course).exists())

    def test_course_reviews_require_enrollment_and_prevent_duplicates(self):
        course, _, _ = self.create_course()
        self.client.force_authenticate(user=self.student)
        denied = self.client.post(
            f"/api/v1/courses/{course.pk}/reviews/",
            {"rating": 5, "content": "Excellent practical course."},
            format="json",
        )
        self.client.post(f"/api/v1/courses/{course.pk}/enroll/")
        review = self.client.post(
            f"/api/v1/courses/{course.pk}/reviews/",
            {"rating": 5, "content": "  Excellent practical course.  "},
            format="json",
        )
        duplicate = self.client.post(
            f"/api/v1/courses/{course.pk}/reviews/",
            {"rating": 4, "content": "Another review."},
            format="json",
        )

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(review.status_code, status.HTTP_201_CREATED)
        self.assertEqual(review.data["content"], "Excellent practical course.")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CourseReview.objects.count(), 1)

    def test_lecturer_management_statistics_are_scoped_to_their_course(self):
        course, _, _ = self.create_course()
        self.client.force_authenticate(user=self.student)
        self.client.post(f"/api/v1/courses/{course.pk}/enroll/")
        self.client.force_authenticate(user=self.lecturer)

        response = self.client.get(
            f"/api/v1/courses/manage/{course.pk}/statistics/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["enrollment_count"], 1)
        self.assertEqual(response.data["in_progress_count"], 1)

        self.client.force_authenticate(user=self.student)
        student_response = self.client.get(
            f"/api/v1/courses/manage/{course.pk}/statistics/"
        )
        self.assertEqual(student_response.status_code, status.HTTP_403_FORBIDDEN)
