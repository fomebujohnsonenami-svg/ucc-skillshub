from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from certificates.models import Certificate
from courses.models import Course, CourseCategory
from portfolios.models import PortfolioProject, StudentPortfolio


class StudentPortfolioApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = self.create_student("student", "Kojo", "Mensah")
        self.other_student = self.create_student("other", "Abena", "Boateng")
        self.category = CourseCategory.objects.create(name="Digital Skills")
        self.course = Course.objects.create(
            title="Data Foundations",
            description="Learn data skills.",
            category=self.category,
            created_by=self.student,
            estimated_duration_minutes=60,
            status=Course.Status.PUBLISHED,
        )

    def create_student(self, username, first_name, last_name):
        return User.objects.create_user(
            email=f"{username}@example.edu",
            password="SecurePassword!2026",
            username=username,
            first_name=first_name,
            last_name=last_name,
            student_email=f"{username}@ucc.edu.gh",
            student_email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
        )

    def test_owner_can_create_edit_and_read_their_portfolio(self):
        self.client.force_authenticate(user=self.student)

        created = self.client.get("/api/v1/portfolio/me/")
        edited = self.client.patch(
            "/api/v1/portfolio/me/",
            {
                "headline": "Data analyst",
                "biography": "I build useful data tools.",
                "academic_programme": "BSc Computer Science",
                "location": "Cape Coast",
            },
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_200_OK)
        self.assertFalse(created.data["is_public"])
        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        self.assertEqual(edited.data["headline"], "Data analyst")
        self.assertEqual(edited.data["full_name"], "Kojo Mensah")
        self.assertEqual(StudentPortfolio.objects.count(), 1)

    def test_private_portfolio_is_hidden_until_owner_enables_public_visibility(self):
        self.client.force_authenticate(user=self.student)
        owner_response = self.client.get("/api/v1/portfolio/me/")
        slug = owner_response.data["slug"]
        private_response = self.client.get(f"/api/v1/portfolio/public/{slug}/")

        self.assertEqual(private_response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.patch(
            "/api/v1/portfolio/me/", {"is_public": True}, format="json"
        )
        public_response = self.client.get(f"/api/v1/portfolio/public/{slug}/")

        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertEqual(public_response.data["full_name"], "Kojo Mensah")
        self.assertNotIn("email", public_response.data)
        self.assertNotIn("student", public_response.data)
        self.assertNotIn("student_id", public_response.data)

    def test_project_crud_is_owner_scoped(self):
        self.client.force_authenticate(user=self.student)
        self.client.get("/api/v1/portfolio/me/")
        created = self.client.post(
            "/api/v1/portfolio/projects/",
            {
                "title": "Portfolio API",
                "description": "A student portfolio service.",
                "category": "Software",
                "skills": ["Django", "REST"],
                "repository_url": "https://github.com/example/portfolio",
            },
            format="json",
        )
        project_id = created.data["id"]
        updated = self.client.patch(
            f"/api/v1/portfolio/projects/{project_id}/",
            {"title": "Portfolio API v2"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["title"], "Portfolio API v2")

        self.client.force_authenticate(user=self.other_student)
        forbidden_update = self.client.patch(
            f"/api/v1/portfolio/projects/{project_id}/",
            {"title": "Stolen project"},
            format="json",
        )
        forbidden_delete = self.client.delete(
            f"/api/v1/portfolio/projects/{project_id}/"
        )
        self.assertEqual(
            forbidden_update.status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            forbidden_delete.status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertTrue(PortfolioProject.objects.filter(pk=project_id).exists())

        self.client.force_authenticate(user=self.student)
        deleted = self.client.delete(f"/api/v1/portfolio/projects/{project_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_skills_and_social_links_can_be_managed_by_the_owner(self):
        self.client.force_authenticate(user=self.student)
        self.client.get("/api/v1/portfolio/me/")
        skill = self.client.post(
            "/api/v1/portfolio/skills/",
            {"name": "Python", "proficiency": "advanced", "category": "Programming"},
            format="json",
        )
        self.client.force_authenticate(
            user=User.objects.get(pk=self.student.pk)
        )
        duplicate_skill = self.client.post(
            "/api/v1/portfolio/skills/",
            {"name": "python", "proficiency": "expert"},
            format="json",
        )
        link = self.client.post(
            "/api/v1/portfolio/social-links/",
            {
                "platform": "website",
                "label": "Portfolio site",
                "url": "https://example.edu/kojo",
            },
            format="json",
        )
        self.client.force_authenticate(
            user=User.objects.get(pk=self.student.pk)
        )
        duplicate_link = self.client.post(
            "/api/v1/portfolio/social-links/",
            {
                "platform": "other",
                "label": "Duplicate website",
                "url": "https://example.edu/kojo",
            },
            format="json",
        )
        updated_link = self.client.patch(
            f"/api/v1/portfolio/social-links/{link.data['id']}/",
            {"label": "Personal website"},
            format="json",
        )

        self.assertEqual(skill.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_skill.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(link.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_link.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(updated_link.data["label"], "Personal website")

        self.client.force_authenticate(user=self.other_student)
        not_owned = self.client.delete(
            f"/api/v1/portfolio/social-links/{link.data['id']}/"
        )
        self.assertEqual(not_owned.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.student)
        removed = self.client.delete(
            f"/api/v1/portfolio/skills/{skill.data['id']}/"
        )
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)

    def test_public_view_filters_private_projects_and_excludes_private_account_data(self):
        portfolio = StudentPortfolio.objects.create(
            student=self.student,
            is_public=True,
            headline="Software developer",
        )
        PortfolioProject.objects.create(
            portfolio=portfolio,
            title="Shared project",
            description="A public project.",
            is_public=True,
        )
        PortfolioProject.objects.create(
            portfolio=portfolio,
            title="Private project",
            description="A draft project.",
            is_public=False,
        )

        response = self.client.get(f"/api/v1/portfolio/public/{portfolio.slug}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [project["title"] for project in response.data["projects"]],
            ["Shared project"],
        )
        self.assertNotIn("email", response.data)
        self.assertNotIn("student_id", response.data)

    def test_only_owned_active_certificates_can_be_showcased(self):
        portfolio = StudentPortfolio.objects.create(student=self.student)
        own_certificate = Certificate.objects.create(
            student=self.student,
            course=self.course,
            issuing_organization="UCC SKILLSHUB",
        )
        other_course = Course.objects.create(
            title="Other Course",
            description="Another course.",
            category=self.category,
            created_by=self.other_student,
            estimated_duration_minutes=60,
            status=Course.Status.PUBLISHED,
        )
        other_certificate = Certificate.objects.create(
            student=self.other_student,
            course=other_course,
        )
        self.client.force_authenticate(user=self.student)

        linked = self.client.post(
            "/api/v1/portfolio/certificates/",
            {"certificate": own_certificate.pk},
            format="json",
        )
        self.client.force_authenticate(
            user=User.objects.get(pk=self.student.pk)
        )
        duplicate = self.client.post(
            "/api/v1/portfolio/certificates/",
            {"certificate": own_certificate.pk},
            format="json",
        )
        not_owned = self.client.post(
            "/api/v1/portfolio/certificates/",
            {"certificate": other_certificate.pk},
            format="json",
        )

        self.assertEqual(linked.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(not_owned.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(portfolio.certificates.count(), 1)

    @override_settings(FRONTEND_BASE_URL="https://app.example.test/sign-in.html")
    def test_share_url_uses_configured_frontend_origin(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get("/api/v1/portfolio/me/")

        self.assertTrue(
            response.data["public_url"].startswith(
                "https://app.example.test/skillbridge_student_portfolio/code.html?slug="
            )
        )
