from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import Course, CourseCategory, CourseModule, Lesson
from pathways.models import (
    PathwayStep,
    PathwayStepProgress,
    Skill,
    SkillCategory,
    SkillPathway,
    StudentPathwayEnrollment,
)


class PathwayApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = SkillCategory.objects.create(
            name="Technology", slug="technology"
        )
        self.lecturer = User.objects.create_user(
            email="lecturer@example.edu",
            password="PathwayPass!2026",
            username="lecturer",
            first_name="Ama",
            last_name="Owusu",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.other_lecturer = User.objects.create_user(
            email="other@example.edu",
            password="PathwayPass!2026",
            username="other",
            first_name="Kofi",
            last_name="Tetteh",
            role=User.Role.LECTURER,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.student = User.objects.create_user(
            email="student@example.edu",
            password="PathwayPass!2026",
            username="student",
            first_name="Kojo",
            last_name="Mensah",
            student_email="student@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.other_student = User.objects.create_user(
            email="second@example.edu",
            password="PathwayPass!2026",
            username="second",
            first_name="Abena",
            last_name="Boateng",
            student_email="second@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )

    def create_pathway(self, name="Data Analyst", difficulty="beginner"):
        self.client.force_authenticate(user=self.lecturer)
        response = self.client.post(
            "/api/v1/pathways/manage/",
            {
                "name": name,
                "description": f"Practical skills for {name.lower()} roles.",
                "category": self.category.pk,
                "difficulty": difficulty,
                "estimated_duration_weeks": 12,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pathway_id = response.data["id"]
        return SkillPathway.objects.get(pk=pathway_id)

    def add_step(self, pathway, title, order=None, **extra):
        payload = {"title": title, "description": f"Learn {title}."}
        if order is not None:
            payload["order"] = order
        payload.update(extra)
        response = self.client.post(
            f"/api/v1/pathways/manage/{pathway.pk}/steps/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def publish(self, pathway):
        return self.client.patch(
            f"/api/v1/pathways/manage/{pathway.pk}/",
            {"status": SkillPathway.Status.PUBLISHED},
            format="json",
        )

    def test_staff_create_steps_and_publish_pathway(self):
        pathway = self.create_pathway()
        self.assertEqual(pathway.created_by, self.lecturer)
        self.assertEqual(pathway.status, SkillPathway.Status.DRAFT)

        first = self.add_step(pathway, "Spreadsheet analysis")
        second = self.add_step(pathway, "SQL foundations")
        published = self.publish(pathway)

        self.assertEqual(published.status_code, status.HTTP_200_OK, published.data)
        self.assertEqual(published.data["status"], SkillPathway.Status.PUBLISHED)
        self.assertEqual(first["order"], 1)
        self.assertEqual(second["order"], 2)

    def test_pathway_cannot_publish_without_a_step(self):
        pathway = self.create_pathway()
        response = self.publish(pathway)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_students_cannot_manage_pathways_or_create_categories(self):
        self.client.force_authenticate(user=self.student)
        pathway_response = self.client.post("/api/v1/pathways/manage/", {})
        category_response = self.client.post(
            "/api/v1/pathways/manage/categories/", {"name": "Business"}
        )
        self.assertEqual(pathway_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(category_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lecturer_management_is_limited_to_owned_pathways(self):
        pathway = self.create_pathway()
        self.client.force_authenticate(user=self.other_lecturer)
        detail = self.client.patch(
            f"/api/v1/pathways/manage/{pathway.pk}/",
            {"name": "Changed name"},
            format="json",
        )
        add_step = self.client.post(
            f"/api/v1/pathways/manage/{pathway.pk}/steps/",
            {"title": "Unauthorized"},
            format="json",
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(add_step.status_code, status.HTTP_404_NOT_FOUND)

    def test_catalogue_search_filters_and_hides_drafts(self):
        first = self.create_pathway("Data Analyst", "beginner")
        self.add_step(first, "Data foundations")
        self.assertEqual(self.publish(first).status_code, status.HTTP_200_OK)
        second = self.create_pathway("Business Administrator", "intermediate")
        self.add_step(second, "Office management")
        self.assertEqual(self.publish(second).status_code, status.HTTP_200_OK)
        self.create_pathway("Unpublished Design Track")

        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/v1/pathways/?search=DATA&category=technology&difficulty=beginner"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], first.pk)

    def test_enrollment_is_unique_and_my_pathways_are_private(self):
        pathway = self.create_pathway()
        self.add_step(pathway, "Skill foundation")
        self.publish(pathway)
        self.client.force_authenticate(user=self.student)
        first = self.client.post(f"/api/v1/pathways/{pathway.pk}/enroll/")
        duplicate = self.client.post(f"/api/v1/pathways/{pathway.pk}/enroll/")
        mine = self.client.get("/api/v1/pathways/my-pathways/")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_200_OK)
        self.assertEqual(StudentPathwayEnrollment.objects.count(), 1)
        self.assertEqual(mine.data["count"], 1)
        self.assertEqual(mine.data["results"][0]["progress_percentage"], 0)
        self.client.force_authenticate(user=self.other_student)
        self.assertEqual(self.client.get("/api/v1/pathways/my-pathways/").data["count"], 0)

    def test_step_completion_calculates_progress_and_completes_pathway(self):
        pathway = self.create_pathway()
        first = self.add_step(pathway, "Research")
        second = self.add_step(pathway, "Present findings")
        self.publish(pathway)
        self.client.force_authenticate(user=self.student)
        self.client.post(f"/api/v1/pathways/{pathway.pk}/enroll/")

        one = self.client.post(
            f"/api/v1/pathway-steps/{first['id']}/complete/"
        )
        two = self.client.post(
            f"/api/v1/pathway-steps/{second['id']}/complete/"
        )
        progress = self.client.get(f"/api/v1/pathways/{pathway.pk}/progress/")

        self.assertEqual(one.status_code, status.HTTP_200_OK)
        self.assertEqual(one.data["progress_percentage"], 50)
        self.assertEqual(two.data["progress_percentage"], 100)
        self.assertEqual(two.data["status"], StudentPathwayEnrollment.Status.COMPLETED)
        self.assertEqual(progress.data["completed_steps"], 2)
        self.assertEqual(len(progress.data["steps"]), 2)
        self.assertEqual(PathwayStepProgress.objects.count(), 2)

    def test_step_completion_requires_enrollment_and_valid_pathway_step(self):
        pathway = self.create_pathway()
        step = self.add_step(pathway, "Secure foundations")
        self.publish(pathway)
        self.client.force_authenticate(user=self.student)

        response = self.client.post(
            f"/api/v1/pathway-steps/{step['id']}/complete/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(f"/api/v1/pathways/{pathway.pk}/progress/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_staff_can_reorder_steps_and_reorder_requires_exact_membership(self):
        pathway = self.create_pathway()
        first = self.add_step(pathway, "First")
        second = self.add_step(pathway, "Second")

        reordered = self.client.post(
            f"/api/v1/pathways/manage/{pathway.pk}/steps/reorder/",
            {"step_ids": [second["id"], first["id"]]},
            format="json",
        )
        invalid = self.client.post(
            f"/api/v1/pathways/manage/{pathway.pk}/steps/reorder/",
            {"step_ids": [second["id"], second["id"]]},
            format="json",
        )

        self.assertEqual(reordered.status_code, status.HTTP_200_OK)
        self.assertEqual([step["id"] for step in reordered.data], [second["id"], first["id"]])
        self.assertEqual([step["order"] for step in reordered.data], [1, 2])
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pathways_can_include_required_skills_courses_and_project_steps(self):
        skill = Skill.objects.create(category=self.category, name="Data analysis")
        course_category = CourseCategory.objects.create(name="Digital", slug="digital")
        course = Course.objects.create(
            title="Data basics",
            description="A published course.",
            category=course_category,
            created_by=self.lecturer,
            estimated_duration_minutes=60,
            status=Course.Status.PUBLISHED,
        )
        pathway = self.create_pathway()
        self.client.patch(
            f"/api/v1/pathways/manage/{pathway.pk}/",
            {
                "required_skill_ids": [skill.pk],
                "recommended_course_ids": [course.pk],
            },
            format="json",
        )
        step = self.add_step(
            pathway,
            "Build a dashboard",
            project_title="Student insights dashboard",
            project_description="Create a small data dashboard.",
            recommended_course=course.pk,
        )
        self.publish(pathway)
        self.client.force_authenticate(user=None)
        detail = self.client.get(f"/api/v1/pathways/{pathway.pk}/")

        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["required_skills"][0]["name"], skill.name)
        self.assertEqual(detail.data["recommended_courses"][0]["id"], course.pk)
        self.assertEqual(detail.data["steps"][0]["project_title"], "Student insights dashboard")
        self.assertEqual(detail.data["steps"][0]["recommended_course"]["id"], course.pk)

    def test_administrator_can_manage_pathways_created_by_lecturers(self):
        pathway = self.create_pathway()
        administrator = User.objects.create_user(
            email="admin@example.edu",
            password="PathwayPass!2026",
            username="admin",
            first_name="Admin",
            last_name="User",
            role=User.Role.ADMINISTRATOR,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=administrator)
        response = self.client.patch(
            f"/api/v1/pathways/manage/{pathway.pk}/",
            {"name": "Updated pathway"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated pathway")
