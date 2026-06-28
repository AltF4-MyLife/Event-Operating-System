from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from . import services
from .models import (
    AIInsight,
    AppVersion,
    AuditLog,
    Badge,
    BackupJob,
    Broadcast,
    Certificate,
    CertificateTemplate,
    CheckInLog,
    Coupon,
    EducationAdministration,
    EmailLog,
    EmailTemplate,
    Event,
    EventDay,
    EventModule,
    Expense,
    Hall,
    IncidentViolation,
    Invoice,
    MediaItem,
    NotificationLog,
    Organization,
    OrganizationSubscription,
    Participant,
    ParticipantBadge,
    ParticipantGroup,
    PointRule,
    PointTransaction,
    RegistrationField,
    RegistrationForm,
    Refund,
    ReportSnapshot,
    SOSReport,
    School,
    Session,
    Speaker,
    Sponsor,
    StudentNote,
    SubscriptionPlan,
    SupportReply,
    SupportTicket,
    Survey,
    SurveyQuestion,
    SurveyResponse,
    Ticket,
    TicketType,
    Track,
    UploadedDocument,
    UserProfile,
    VIPInvitation,
    ViolationType,
    Volunteer,
    VolunteerShift,
    Workshop,
    WorkshopRegistration,
)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="profile.role", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class EventModuleSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="get_code_display", read_only=True)

    class Meta:
        model = EventModule
        fields = "__all__"


class EventSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    modules_count = serializers.IntegerField(source="modules.count", read_only=True)

    class Meta:
        model = Event
        fields = "__all__"


class RegistrationFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationField
        fields = "__all__"


class RegistrationFormSerializer(serializers.ModelSerializer):
    fields = RegistrationFieldSerializer(many=True, read_only=True)

    class Meta:
        model = RegistrationForm
        fields = "__all__"


class ParticipantSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source="event.name", read_only=True)
    points_total = serializers.SerializerMethodField()
    attendance_percent = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = "__all__"
    read_only_fields = ["tracking_code", "qr_code", "duplicate_hash", "approved_at", "checked_in_at", "checked_out_at"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_points_total(self, obj):
        return services.participant_points_total(obj)

    @extend_schema_field(OpenApiTypes.INT)
    def get_attendance_percent(self, obj):
        return services.attendance_percent(obj)


class PublicRegistrationSerializer(serializers.Serializer):
    registration_type = serializers.ChoiceField(choices=Participant.RegistrationType.choices, default=Participant.RegistrationType.STUDENT)
    full_name = serializers.CharField(max_length=180)
    phone = serializers.CharField(max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True)
    governorate = serializers.CharField(required=False, allow_blank=True)
    national_id = serializers.CharField(required=False, allow_blank=True)
    age = serializers.IntegerField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    guardian_name = serializers.CharField(required=False, allow_blank=True)
    guardian_phone = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    dynamic_answers = serializers.JSONField(required=False)

    def create(self, validated_data):
        return services.register_participant(self.context["event"], validated_data, request=self.context.get("request"))


class CheckInSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=140)
    gate = serializers.CharField(max_length=120, required=False, allow_blank=True)
    device = serializers.CharField(max_length=120, required=False, allow_blank=True)
    action = serializers.ChoiceField(choices=CheckInLog.Action.choices, default=CheckInLog.Action.CHECKIN)
    workshop = serializers.PrimaryKeyRelatedField(queryset=Workshop.objects.all(), required=False, allow_null=True)


class WorkshopSerializer(serializers.ModelSerializer):
    seats_taken = serializers.IntegerField(read_only=True)
    seats_available = serializers.IntegerField(read_only=True)

    class Meta:
        model = Workshop
        fields = "__all__"


class WorkshopRegistrationSerializer(serializers.ModelSerializer):
    participant_name = serializers.CharField(source="participant.full_name", read_only=True)
    workshop_title = serializers.CharField(source="workshop.title", read_only=True)

    class Meta:
        model = WorkshopRegistration
        fields = "__all__"


class CertificateSerializer(serializers.ModelSerializer):
    participant_name = serializers.CharField(source="participant.full_name", read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)
    verify_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = "__all__"

    @extend_schema_field(OpenApiTypes.URI)
    def get_verify_url(self, obj):
        request = self.context.get("request")
        path = f"/certificates/verify/{obj.verification_code}/"
        return request.build_absolute_uri(path) if request else path


class SupportTicketSerializer(serializers.ModelSerializer):
    replies = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = "__all__"
        read_only_fields = ["tracking_code"]


class SimpleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = "__all__"


class UserProfileSerializer(SimpleModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"


class EventDaySerializer(SimpleModelSerializer):
    class Meta:
        model = EventDay
        fields = "__all__"


class TrackSerializer(SimpleModelSerializer):
    class Meta:
        model = Track
        fields = "__all__"


class HallSerializer(SimpleModelSerializer):
    class Meta:
        model = Hall
        fields = "__all__"


class EducationAdministrationSerializer(SimpleModelSerializer):
    class Meta:
        model = EducationAdministration
        fields = "__all__"


class SchoolSerializer(SimpleModelSerializer):
    class Meta:
        model = School
        fields = "__all__"


class ParticipantGroupSerializer(SimpleModelSerializer):
    class Meta:
        model = ParticipantGroup
        fields = "__all__"


class UploadedDocumentSerializer(SimpleModelSerializer):
    class Meta:
        model = UploadedDocument
        fields = "__all__"


class SpeakerSerializer(SimpleModelSerializer):
    class Meta:
        model = Speaker
        fields = "__all__"


class SessionSerializer(SimpleModelSerializer):
    class Meta:
        model = Session
        fields = "__all__"


class CheckInLogSerializer(SimpleModelSerializer):
    class Meta:
        model = CheckInLog
        fields = "__all__"


class StudentNoteSerializer(SimpleModelSerializer):
    class Meta:
        model = StudentNote
        fields = "__all__"


class PointRuleSerializer(SimpleModelSerializer):
    class Meta:
        model = PointRule
        fields = "__all__"


class PointTransactionSerializer(SimpleModelSerializer):
    class Meta:
        model = PointTransaction
        fields = "__all__"


class BadgeSerializer(SimpleModelSerializer):
    class Meta:
        model = Badge
        fields = "__all__"


class ParticipantBadgeSerializer(SimpleModelSerializer):
    class Meta:
        model = ParticipantBadge
        fields = "__all__"


class ViolationTypeSerializer(SimpleModelSerializer):
    class Meta:
        model = ViolationType
        fields = "__all__"


class IncidentViolationSerializer(SimpleModelSerializer):
    class Meta:
        model = IncidentViolation
        fields = "__all__"


class CertificateTemplateSerializer(SimpleModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = "__all__"


class EmailTemplateSerializer(SimpleModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = "__all__"


class EmailLogSerializer(SimpleModelSerializer):
    class Meta:
        model = EmailLog
        fields = "__all__"


class NotificationLogSerializer(SimpleModelSerializer):
    class Meta:
        model = NotificationLog
        fields = "__all__"


class BroadcastSerializer(SimpleModelSerializer):
    class Meta:
        model = Broadcast
        fields = "__all__"


class SOSReportSerializer(SimpleModelSerializer):
    class Meta:
        model = SOSReport
        fields = "__all__"


class SupportReplySerializer(SimpleModelSerializer):
    class Meta:
        model = SupportReply
        fields = "__all__"


class VolunteerSerializer(SimpleModelSerializer):
    class Meta:
        model = Volunteer
        fields = "__all__"


class VolunteerShiftSerializer(SimpleModelSerializer):
    class Meta:
        model = VolunteerShift
        fields = "__all__"


class VIPInvitationSerializer(SimpleModelSerializer):
    class Meta:
        model = VIPInvitation
        fields = "__all__"


class SponsorSerializer(SimpleModelSerializer):
    class Meta:
        model = Sponsor
        fields = "__all__"


class MediaItemSerializer(SimpleModelSerializer):
    class Meta:
        model = MediaItem
        fields = "__all__"


class SurveySerializer(SimpleModelSerializer):
    class Meta:
        model = Survey
        fields = "__all__"


class SurveyQuestionSerializer(SimpleModelSerializer):
    class Meta:
        model = SurveyQuestion
        fields = "__all__"


class SurveyResponseSerializer(SimpleModelSerializer):
    class Meta:
        model = SurveyResponse
        fields = "__all__"


class TicketTypeSerializer(SimpleModelSerializer):
    class Meta:
        model = TicketType
        fields = "__all__"


class CouponSerializer(SimpleModelSerializer):
    class Meta:
        model = Coupon
        fields = "__all__"


class TicketSerializer(SimpleModelSerializer):
    class Meta:
        model = Ticket
        fields = "__all__"


class InvoiceSerializer(SimpleModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"


class RefundSerializer(SimpleModelSerializer):
    class Meta:
        model = Refund
        fields = "__all__"


class ExpenseSerializer(SimpleModelSerializer):
    class Meta:
        model = Expense
        fields = "__all__"


class ReportSnapshotSerializer(SimpleModelSerializer):
    class Meta:
        model = ReportSnapshot
        fields = "__all__"


class AppVersionSerializer(SimpleModelSerializer):
    class Meta:
        model = AppVersion
        fields = "__all__"


class AIInsightSerializer(SimpleModelSerializer):
    class Meta:
        model = AIInsight
        fields = "__all__"


class BackupJobSerializer(SimpleModelSerializer):
    class Meta:
        model = BackupJob
        fields = "__all__"


class SubscriptionPlanSerializer(SimpleModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"


class OrganizationSubscriptionSerializer(SimpleModelSerializer):
    class Meta:
        model = OrganizationSubscription
        fields = "__all__"


class AuditLogSerializer(SimpleModelSerializer):
    ip_address = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "actor",
            "action",
            "entity_type",
            "entity_id",
            "organization",
            "event",
            "ip_address",
            "user_agent",
            "before",
            "after",
            "note",
        )
