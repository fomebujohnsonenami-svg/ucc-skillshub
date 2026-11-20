from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

from certificates.models import Achievement, Certificate, StudentAchievement
from courses.models import CourseEnrollment, LessonProgress
from pathways.models import PathwayStepProgress, StudentPathwayEnrollment
from notifications.services import create_notification


ISSUER_NAME = "UCC SKILLSHUB"


def _render_certificate_pdf(certificate):
    buffer = BytesIO()
    page_width, page_height = landscape(letter)
    document = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    document.setTitle(f"Certificate {certificate.certificate_id}")
    document.setStrokeColor(colors.HexColor("#b28a3b"))
    document.setLineWidth(3)
    document.roundRect(28, 28, page_width - 56, page_height - 56, 12)
    document.setStrokeColor(colors.HexColor("#e4d3a9"))
    document.setLineWidth(1)
    document.roundRect(38, 38, page_width - 76, page_height - 76, 8)

    document.setFillColor(colors.HexColor("#173b57"))
    document.setFont("Helvetica-Bold", 18)
    document.drawCentredString(page_width / 2, page_height - 92, ISSUER_NAME)
    document.setFillColor(colors.HexColor("#8b6a2e"))
    document.setFont("Helvetica-Bold", 12)
    document.drawCentredString(page_width / 2, page_height - 133, "CERTIFICATE OF COMPLETION")
    document.setFillColor(colors.HexColor("#454545"))
    document.setFont("Helvetica", 12)
    document.drawCentredString(page_width / 2, page_height - 169, "This certificate is presented to")
    document.setFillColor(colors.HexColor("#173b57"))
    document.setFont("Helvetica-Bold", 25)
    document.drawCentredString(
        page_width / 2,
        page_height - 211,
        certificate.student.get_full_name() or certificate.student.username,
    )
    document.setFillColor(colors.HexColor("#454545"))
    document.setFont("Helvetica", 12)
    document.drawCentredString(page_width / 2, page_height - 248, "for completing")
    document.setFillColor(colors.HexColor("#173b57"))
    document.setFont("Helvetica-Bold", 20)
    document.drawCentredString(
        page_width / 2, page_height - 282, certificate.learning_item_name[:90]
    )
    completed_at = certificate.completion_info.get("completed_at", "")
    document.setFillColor(colors.HexColor("#454545"))
    document.setFont("Helvetica", 10)
    document.drawCentredString(
        page_width / 2,
        112,
        f"Issued {certificate.issue_date.isoformat()}  |  Completed {completed_at[:10]}",
    )
    document.setFont("Helvetica-Bold", 9)
    document.drawCentredString(page_width / 2, 91, certificate.certificate_id)
    document.setFont("Helvetica", 8)
    document.drawCentredString(
        page_width / 2,
        73,
        f"Verify: /certificates/verify/{certificate.verification_token}/",
    )
    document.save()
    return buffer.getvalue()


def _save_certificate_file(certificate):
    filename = f"{certificate.certificate_id.lower()}.pdf"
    certificate.certificate_file.save(
        filename, ContentFile(_render_certificate_pdf(certificate)), save=True
    )


@transaction.atomic
def issue_course_certificate(enrollment):
    course = enrollment.course
    if (
        not course.certificate_eligible
        or enrollment.status != CourseEnrollment.Status.COMPLETED
        or not enrollment.completed_at
    ):
        return None

    certificate, created = Certificate.objects.get_or_create(
        student=enrollment.student,
        course=course,
        defaults={
            "issuing_organization": ISSUER_NAME,
            "completion_info": {
                "completed_at": enrollment.completed_at.isoformat(),
                "completion_status": enrollment.status,
            },
        },
    )
    if created:
        _save_certificate_file(certificate)
        create_notification(
            certificate.student,
            title="Certificate earned",
            message=f"You earned a certificate for {certificate.learning_item_name}.",
            notification_type="certificate_issued",
            related_resource=certificate,
            target_url=f"/certificates/{certificate.pk}/",
        )
    return certificate


@transaction.atomic
def issue_pathway_certificate(enrollment):
    if (
        enrollment.status != StudentPathwayEnrollment.Status.COMPLETED
        or not enrollment.completed_at
        or not enrollment.pathway.steps.exists()
    ):
        return None

    total_steps = enrollment.pathway.steps.count()
    completed_steps = PathwayStepProgress.objects.filter(
        enrollment=enrollment, is_completed=True
    ).count()
    if completed_steps != total_steps:
        return None

    certificate, created = Certificate.objects.get_or_create(
        student=enrollment.student,
        pathway=enrollment.pathway,
        defaults={
            "issuing_organization": ISSUER_NAME,
            "completion_info": {
                "completed_at": enrollment.completed_at.isoformat(),
                "completion_status": enrollment.status,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
            },
        },
    )
    if created:
        _save_certificate_file(certificate)
        create_notification(
            certificate.student,
            title="Certificate earned",
            message=f"You earned a certificate for {certificate.learning_item_name}.",
            notification_type="certificate_issued",
            related_resource=certificate,
            target_url=f"/certificates/{certificate.pk}/",
        )
    return certificate


def _learning_streak_days(student):
    activity_dates = set()
    for completed_at in LessonProgress.objects.filter(
        enrollment__student=student, is_completed=True
    ).values_list("completed_at", flat=True):
        if completed_at:
            activity_dates.add(timezone.localtime(completed_at).date())
    for completed_at in PathwayStepProgress.objects.filter(
        enrollment__student=student, is_completed=True
    ).values_list("completed_at", flat=True):
        if completed_at:
            activity_dates.add(timezone.localtime(completed_at).date())
    if not activity_dates:
        return 0

    cursor = max(activity_dates)
    streak = 0
    while cursor in activity_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _criteria_met(criteria, event, course_count, pathway_count, streak_days):
    criterion = criteria.get("type")

    if criterion == "first_course_completed":
        return course_count >= 1
    if criterion == "multiple_courses_completed":
        return course_count >= max(1, int(criteria.get("count", 3)))
    if criterion == "learning_champion":
        return course_count >= max(1, int(criteria.get("count", 10)))
    if criterion == "pathway_completed":
        return pathway_count >= 1
    if criterion == "learning_streak":
        return streak_days >= max(1, int(criteria.get("days", 7)))
    if criterion == "project_approved":
        return event == "project_approved"
    return False


def award_achievements(student, event=None):
    awards = []
    achievements = list(Achievement.objects.filter(is_active=True))
    existing = set(
        StudentAchievement.objects.filter(
            student=student, achievement__in=achievements
        ).values_list("achievement_id", flat=True)
    )
    course_count = None
    pathway_count = None
    streak_days = None
    for achievement in achievements:
        if achievement.pk in existing:
            continue
        criterion = achievement.award_criteria.get("type")
        if criterion in {
            "first_course_completed",
            "multiple_courses_completed",
            "learning_champion",
        } and course_count is None:
            course_count = CourseEnrollment.objects.filter(
                student=student, status=CourseEnrollment.Status.COMPLETED
            ).count()
        if criterion == "pathway_completed" and pathway_count is None:
            pathway_count = StudentPathwayEnrollment.objects.filter(
                student=student, status=StudentPathwayEnrollment.Status.COMPLETED
            ).count()
        if criterion == "learning_streak" and streak_days is None:
            streak_days = _learning_streak_days(student)
        if not _criteria_met(
            achievement.award_criteria,
            event,
            course_count or 0,
            pathway_count or 0,
            streak_days or 0,
        ):
            continue
        award, created = StudentAchievement.objects.get_or_create(
            student=student, achievement=achievement
        )
        if created:
            create_notification(
                student,
                title="Achievement unlocked",
                message=f"You earned {achievement.name}.",
                notification_type="achievement_awarded",
                related_resource=award,
                target_url="/achievements/my-achievements/",
            )
            awards.append(award)
    return awards
