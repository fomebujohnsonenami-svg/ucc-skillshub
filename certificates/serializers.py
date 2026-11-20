from rest_framework import serializers

from certificates.models import Achievement, Certificate, StudentAchievement


class CertificateSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SerializerMethodField()
    learning_item = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "id",
            "certificate_id",
            "certificate_type",
            "learning_item",
            "issuing_organization",
            "issue_date",
            "completion_info",
            "verification_url",
            "download_url",
        )
        read_only_fields = fields

    def get_certificate_type(self, certificate):
        return "course" if certificate.course_id else "pathway"

    def get_learning_item(self, certificate):
        if certificate.course_id:
            return {"id": certificate.course_id, "name": certificate.course.title}
        return {"id": certificate.pathway_id, "name": certificate.pathway.name}

    def get_download_url(self, certificate):
        request = self.context.get("request")
        url = f"/api/v1/certificates/{certificate.pk}/download/"
        return request.build_absolute_uri(url) if request else url

    def get_verification_url(self, certificate):
        request = self.context.get("request")
        url = f"/certificates/verify/{certificate.verification_token}/"
        return request.build_absolute_uri(url) if request else url


class PublicCertificateVerificationSerializer(serializers.ModelSerializer):
    certificate_type = serializers.SerializerMethodField()
    learning_item = serializers.SerializerMethodField()
    recipient = serializers.SerializerMethodField()
    valid = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            "valid",
            "certificate_id",
            "certificate_type",
            "learning_item",
            "recipient",
            "issuing_organization",
            "issue_date",
            "completion_info",
        )
        read_only_fields = fields

    def get_certificate_type(self, certificate):
        return "course" if certificate.course_id else "pathway"

    def get_learning_item(self, certificate):
        if certificate.course_id:
            return certificate.course.title
        return certificate.pathway.name

    def get_recipient(self, certificate):
        user = certificate.student
        last_initial = f" {user.last_name[:1]}." if user.last_name else ""
        return f"{user.first_name}{last_initial}"

    def get_valid(self, certificate):
        return not certificate.is_revoked


class AchievementSerializer(serializers.ModelSerializer):
    earned = serializers.SerializerMethodField()
    awarded_at = serializers.SerializerMethodField()

    class Meta:
        model = Achievement
        fields = (
            "id",
            "key",
            "name",
            "description",
            "badge_image",
            "award_criteria",
            "category",
            "earned",
            "awarded_at",
        )
        read_only_fields = fields

    def get_earned(self, achievement):
        if "award_ids" not in self.context:
            return True
        award_ids = self.context["award_ids"]
        return achievement.pk in award_ids

    def get_awarded_at(self, achievement):
        awarded_at = self.context.get("awarded_at", {})
        return awarded_at.get(achievement.pk)


class StudentAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)

    class Meta:
        model = StudentAchievement
        fields = ("achievement", "awarded_at")
        read_only_fields = fields
