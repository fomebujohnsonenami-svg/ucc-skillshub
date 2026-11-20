from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import EmployerProfile, RoleApproval, User
from opportunities.models import (
    ApplicationAttachment,
    Opportunity,
    OpportunityApplication,
    OpportunityCategory,
    OpportunitySkill,
)
from notifications.models import Notification
from portfolios.models import StudentPortfolio


class OpportunityApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = self.create_user(
            "student",
            User.Role.STUDENT,
            student_email="student@ucc.edu.gh",
            student_email_verified=True,
        )
        self.other_student = self.create_user(
            "other",
            User.Role.STUDENT,
            student_email="other@ucc.edu.gh",
            student_email_verified=True,
        )
        self.manager = self.create_user("manager", User.Role.EMPLOYER)
        EmployerProfile.objects.create(
            user=self.manager, organization_name="Acme Ltd"
        )
        self.other_manager = self.create_user("other-manager", User.Role.EMPLOYER)
        EmployerProfile.objects.create(
            user=self.other_manager, organization_name="Other Ltd"
        )
        self.internships = OpportunityCategory.objects.get(slug="internships")
        self.campus_jobs = OpportunityCategory.objects.get(slug="campus-jobs")

    def create_user(self, username, role, **extra_fields):
        account_status = extra_fields.pop(
            "account_status", User.AccountStatus.ACTIVE
        )
        return User.objects.create_user(
            email=f"{username}@example.com",
            password="SecurePassword!2026",
            username=username,
            first_name=username.title(),
            last_name="User",
            role=role,
            account_status=account_status,
            **extra_fields,
        )

    def create_opportunity(self, **overrides):
        values = {
            "category": self.internships,
            "title": "Python Intern",
            "organization": "Acme Ltd",
            "description": "Build useful data tools.",
            "responsibilities": "Write and maintain Python services.",
            "requirements": "Share a short statement.",
            "location": "Accra",
            "work_arrangement": Opportunity.WorkArrangement.REMOTE,
            "opportunity_type": "internship",
            "application_deadline": timezone.now() + timedelta(days=14),
            "status": Opportunity.PublicationStatus.PUBLISHED,
            "created_by": self.manager,
        }
        values.update(overrides)
        opportunity = Opportunity.objects.create(**values)
        opportunity.required_skills.add(
            OpportunitySkill.objects.get_or_create(name="Python")[0]
        )
        return opportunity

    def test_public_catalog_search_and_filters_return_only_open_matches(self):
        matching = self.create_opportunity()
        self.create_opportunity(
            category=self.campus_jobs,
            title="Campus Assistant",
            organization="UCC",
            location="Cape Coast",
            work_arrangement=Opportunity.WorkArrangement.ONSITE,
            opportunity_type="part-time",
        )
        self.create_opportunity(
            title="Draft role",
            status=Opportunity.PublicationStatus.DRAFT,
        )
        self.create_opportunity(
            title="Expired role",
            application_deadline=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(
            "/api/v1/opportunities/?search=ACME&category=internships"
            "&location=Accra&skills=python&work_arrangement=remote"
            "&opportunity_type=INTERNSHIP"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual([item["id"] for item in results], [matching.pk])
        self.assertEqual(results[0]["required_skills"][0]["name"], "Python")
        self.assertFalse(results[0]["is_applied"])

    def test_public_detail_hides_unpublished_opportunities(self):
        draft = self.create_opportunity(status=Opportunity.PublicationStatus.DRAFT)

        response = self.client.get(f"/api/v1/opportunities/{draft.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_application_is_unique_and_owned(self):
        opportunity = self.create_opportunity()
        portfolio = StudentPortfolio.objects.create(student=self.student)
        self.client.force_authenticate(user=self.student)

        applied = self.client.post(
            f"/api/v1/opportunities/{opportunity.pk}/apply/",
            {"statement": "I would like to contribute.", "portfolio": portfolio.pk},
            format="json",
        )
        duplicate = self.client.post(
            f"/api/v1/opportunities/{opportunity.pk}/apply/",
            {"statement": "A second submission."},
            format="json",
        )
        application_id = applied.data["id"]

        self.assertEqual(applied.status_code, status.HTTP_201_CREATED, applied.data)
        self.assertEqual(applied.data["status"], OpportunityApplication.Status.APPLIED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OpportunityApplication.objects.count(), 1)

        self.client.force_authenticate(user=self.other_student)
        hidden = self.client.get(
            f"/api/v1/opportunities/applications/{application_id}/"
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.student)
        forbidden_decision = self.client.patch(
            f"/api/v1/opportunities/applications/{application_id}/status/",
            {"status": OpportunityApplication.Status.ACCEPTED},
            format="json",
        )
        self.assertEqual(
            forbidden_decision.status_code, status.HTTP_403_FORBIDDEN
        )

    @patch("accounts.storage.create_signed_url", return_value="https://signed.test/file")
    @patch("opportunities.views.upload_private_file")
    def test_attachments_use_private_storage_and_signed_downloads(
        self, upload_mock, signed_url_mock
    ):
        opportunity = self.create_opportunity()
        self.client.force_authenticate(user=self.student)
        document = SimpleUploadedFile(
            "resume.pdf", b"%PDF-1.7\nsample pdf bytes", content_type="application/pdf"
        )

        response = self.client.post(
            f"/api/v1/opportunities/{opportunity.pk}/apply/",
            {
                "statement": "Please consider my application.",
                "attachments": [document],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        attachment = ApplicationAttachment.objects.get()
        upload_mock.assert_called_once()
        self.assertEqual(upload_mock.call_args.args[0], "application_attachments")
        self.assertEqual(attachment.file_name, "resume.pdf")
        self.assertEqual(
            response.data["attachments"][0]["download_url"], "https://signed.test/file"
        )
        signed_url_mock.assert_called_once_with(
            "application_attachments", attachment.object_path
        )

    def test_unsupported_attachments_are_rejected_before_application_creation(self):
        opportunity = self.create_opportunity()
        self.client.force_authenticate(user=self.student)
        document = SimpleUploadedFile(
            "payload.exe", b"not allowed", content_type="application/octet-stream"
        )

        response = self.client.post(
            f"/api/v1/opportunities/{opportunity.pk}/apply/",
            {
                "statement": "Please consider my application.",
                "attachments": [document],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OpportunityApplication.objects.exists())

    def test_manager_can_review_only_applications_for_their_organization(self):
        own_opportunity = self.create_opportunity()
        other_opportunity = self.create_opportunity(
            title="Other role",
            organization="Other Ltd",
            created_by=self.other_manager,
        )
        own_application = OpportunityApplication.objects.create(
            opportunity=own_opportunity,
            student=self.student,
            statement="My application.",
        )
        other_application = OpportunityApplication.objects.create(
            opportunity=other_opportunity,
            student=self.other_student,
            statement="Another application.",
        )
        self.client.force_authenticate(user=self.manager)

        applications = self.client.get("/api/v1/opportunities/applications/")
        accepted = self.client.patch(
            f"/api/v1/opportunities/applications/{own_application.pk}/status/",
            {
                "status": OpportunityApplication.Status.SHORTLISTED,
                "review_note": "Invite for interview.",
            },
            format="json",
        )
        reset = self.client.patch(
            f"/api/v1/opportunities/applications/{own_application.pk}/status/",
            {"status": OpportunityApplication.Status.APPLIED},
            format="json",
        )
        unrelated = self.client.patch(
            f"/api/v1/opportunities/applications/{other_application.pk}/status/",
            {"status": OpportunityApplication.Status.ACCEPTED},
            format="json",
        )

        self.assertEqual(applications.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in applications.data["results"]],
            [own_application.pk],
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK, accepted.data)
        self.assertEqual(
            accepted.data["status"], OpportunityApplication.Status.SHORTLISTED
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.Type.APPLICATION_STATUS,
            ).count(),
            1,
        )
        self.assertEqual(reset.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            OpportunityApplication.objects.get(pk=own_application.pk).reviewed_by,
            self.manager,
        )
        self.assertEqual(unrelated.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            OpportunityApplication.objects.get(pk=other_application.pk).status,
            OpportunityApplication.Status.APPLIED,
        )

    def test_manager_listing_and_creation_are_organization_scoped(self):
        self.create_opportunity()
        self.create_opportunity(
            organization="Other Ltd", created_by=self.other_manager
        )
        self.client.force_authenticate(user=self.manager)

        listings = self.client.get("/api/v1/opportunities/manage/")
        invalid_create = self.client.post(
            "/api/v1/opportunities/manage/",
            {
                "category": self.internships.pk,
                "title": "Impersonated role",
                "organization": "Other Ltd",
                "description": "Not this organization.",
                "application_deadline": (
                    timezone.now() + timedelta(days=7)
                ).isoformat(),
            },
            format="json",
        )
        valid_create = self.client.post(
            "/api/v1/opportunities/manage/",
            {
                "category": self.internships.pk,
                "title": "New role",
                "description": "A role for our organization.",
                "application_deadline": (
                    timezone.now() + timedelta(days=7)
                ).isoformat(),
                "required_skill_names": ["Django", "Python"],
            },
            format="json",
        )

        self.assertEqual(listings.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["organization"] for item in listings.data["results"]],
            ["Acme Ltd"],
        )
        self.assertEqual(invalid_create.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            valid_create.status_code, status.HTTP_201_CREATED, valid_create.data
        )
        created = Opportunity.objects.get(pk=valid_create.data["id"])
        self.assertEqual(created.organization, "Acme Ltd")
        published = self.client.patch(
            f"/api/v1/opportunities/manage/{created.pk}/",
            {"status": Opportunity.PublicationStatus.PUBLISHED},
            format="json",
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK, published.data)
        self.assertEqual(
            Notification.objects.filter(
                notification_type=Notification.Type.NEW_OPPORTUNITY
            ).count(),
            2,
        )
        self.assertEqual(
            set(created.required_skills.values_list("name", flat=True)),
            {"Django", "Python"},
        )

    def test_inactive_manager_cannot_review_applications(self):
        opportunity = self.create_opportunity()
        application = OpportunityApplication.objects.create(
            opportunity=opportunity,
            student=self.student,
            statement="My application.",
        )
        inactive_manager = self.create_user(
            "inactive-manager",
            User.Role.EMPLOYER,
            account_status=User.AccountStatus.SUSPENDED,
        )
        EmployerProfile.objects.create(
            user=inactive_manager, organization_name="Acme Ltd"
        )
        self.client.force_authenticate(user=inactive_manager)

        response = self.client.patch(
            f"/api/v1/opportunities/applications/{application.pk}/status/",
            {"status": OpportunityApplication.Status.REJECTED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            OpportunityApplication.objects.get(pk=application.pk).status,
            OpportunityApplication.Status.APPLIED,
        )

    def test_recruiter_must_be_approved_before_managing_opportunities(self):
        recruiter = self.create_user("recruiter", User.Role.RECRUITER)
        EmployerProfile.objects.create(
            user=recruiter, organization_name="Recruitment Co"
        )
        approval = RoleApproval.objects.create(
            user=recruiter, status=RoleApproval.Status.PENDING
        )
        self.client.force_authenticate(user=recruiter)

        pending_response = self.client.get("/api/v1/opportunities/manage/")
        approval.status = RoleApproval.Status.APPROVED
        approval.save(update_fields=("status",))
        approved_response = self.client.get("/api/v1/opportunities/manage/")

        self.assertEqual(pending_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(approved_response.status_code, status.HTTP_200_OK)

    def test_non_student_cannot_apply(self):
        opportunity = self.create_opportunity()
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            f"/api/v1/opportunities/{opportunity.pk}/apply/",
            {"statement": "I would like to apply."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
