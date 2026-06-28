from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models as django_models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    RegistrationStatus,
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
from .permissions import EventOSPermission, scope_queryset
from .serializers import (
    AIInsightSerializer,
    AppVersionSerializer,
    AuditLogSerializer,
    BackupJobSerializer,
    BadgeSerializer,
    BroadcastSerializer,
    CertificateSerializer,
    CertificateTemplateSerializer,
    CheckInLogSerializer,
    CheckInSerializer,
    CouponSerializer,
    EducationAdministrationSerializer,
    EmailLogSerializer,
    EmailTemplateSerializer,
    EventDaySerializer,
    EventModuleSerializer,
    EventSerializer,
    ExpenseSerializer,
    HallSerializer,
    IncidentViolationSerializer,
    InvoiceSerializer,
    MediaItemSerializer,
    NotificationLogSerializer,
    OrganizationSerializer,
    OrganizationSubscriptionSerializer,
    ParticipantBadgeSerializer,
    ParticipantGroupSerializer,
    ParticipantSerializer,
    PointRuleSerializer,
    PointTransactionSerializer,
    PublicRegistrationSerializer,
    RegistrationFieldSerializer,
    RegistrationFormSerializer,
    RefundSerializer,
    ReportSnapshotSerializer,
    SOSReportSerializer,
    SchoolSerializer,
    SessionSerializer,
    SpeakerSerializer,
    SponsorSerializer,
    StudentNoteSerializer,
    SubscriptionPlanSerializer,
    SupportReplySerializer,
    SupportTicketSerializer,
    SurveyQuestionSerializer,
    SurveyResponseSerializer,
    SurveySerializer,
    TicketSerializer,
    TicketTypeSerializer,
    TrackSerializer,
    UploadedDocumentSerializer,
    UserProfileSerializer,
    VIPInvitationSerializer,
    ViolationTypeSerializer,
    VolunteerSerializer,
    VolunteerShiftSerializer,
    WorkshopRegistrationSerializer,
    WorkshopSerializer,
)


def api_error(exc):
    message = exc.messages if hasattr(exc, "messages") else str(exc)
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


class BaseScopedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [EventOSPermission]
    ordering_fields = "__all__"

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(queryset.model, "is_deleted"):
            queryset = queryset.filter(is_deleted=False)
        queryset = scope_queryset(self.request.user, queryset)
        if not queryset.ordered:
            field_names = {field.name for field in queryset.model._meta.fields}
            queryset = queryset.order_by("-created_at" if "created_at" in field_names else "pk")
        return queryset

    def perform_create(self, serializer):
        obj = serializer.save()
        services.audit(f"{obj.__class__.__name__.lower()}.created", obj, actor=self.request.user, request=self.request)

    def perform_update(self, serializer):
        before = {}
        if serializer.instance:
            before = {field: getattr(serializer.instance, field, None) for field in serializer.validated_data.keys()}
        obj = serializer.save()
        services.audit(f"{obj.__class__.__name__.lower()}.updated", obj, actor=self.request.user, before=before, after=serializer.validated_data, request=self.request)


class OrganizationViewSet(BaseScopedModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    search_fields = ["name", "slug", "contact_email", "contact_phone"]
    filterset_fields = ["is_active"]


class EventViewSet(BaseScopedModelViewSet):
    queryset = Event.objects.select_related("organization").all()
    serializer_class = EventSerializer
    search_fields = ["name", "slug", "organization__name", "venue_name"]
    filterset_fields = ["organization", "event_type", "registration_open", "maintenance_mode", "archived"]

    def perform_create(self, serializer):
        event = serializer.save()
        services.ensure_default_modules(event, actor=self.request.user)
        services.ensure_registration_form(event)
        services.audit("event.created", event, actor=self.request.user, request=self.request)

    @action(detail=True, methods=["get", "post"])
    def modules(self, request, pk=None):
        event = self.get_object()
        services.ensure_default_modules(event, actor=request.user)
        if request.method == "POST":
            module = get_object_or_404(EventModule, event=event, code=request.data.get("code"))
            before = {"enabled": module.enabled}
            module.enabled = bool(request.data.get("enabled", not module.enabled))
            module.changed_by = request.user
            module.save()
            services.audit("module.toggled", module, actor=request.user, before=before, after={"enabled": module.enabled}, request=request)
        serializer = EventModuleSerializer(event.modules.all(), many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        return Response(services.dashboard_stats(event=self.get_object()))

    @action(detail=True, methods=["post"])
    def duplicate_insights(self, request, pk=None):
        insights = services.rule_based_duplicate_insights(self.get_object())
        return Response(AIInsightSerializer(insights, many=True, context={"request": request}).data)


class ParticipantViewSet(BaseScopedModelViewSet):
    queryset = Participant.objects.select_related("event", "school", "education_administration", "group").all()
    serializer_class = ParticipantSerializer
    search_fields = ["full_name", "phone", "email", "tracking_code", "qr_code", "national_id", "school__name"]
    filterset_fields = ["event", "status", "registration_type", "governorate", "school", "education_administration", "group"]

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        try:
            participant = services.review_participant(self.get_object(), request.data.get("action"), actor=request.user, note=request.data.get("note", ""), request=request)
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(self.get_serializer(participant).data)

    @action(detail=False, methods=["post"])
    def bulk_review(self, request):
        ids = request.data.get("ids", [])
        if isinstance(ids, str):
            ids = [item for item in ids.split(",") if item]
        participants = self.get_queryset().filter(pk__in=ids)
        if not ids:
            return Response({"detail": "ids is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            count = services.bulk_review_participants(participants, request.data.get("action"), actor=request.user, note=request.data.get("note", ""), request=request)
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response({"updated": count})

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_workbook(self, request):
        event = get_object_or_404(scope_queryset(request.user, Event.objects.all()), pk=request.data.get("event"))
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = services.import_participants_workbook(
                event,
                upload,
                actor=request.user,
                request=request,
                default_status=request.data.get("default_status", RegistrationStatus.SUBMITTED),
            )
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(result)

    @action(detail=False, methods=["post"])
    def checkin(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(scope_queryset(request.user, Event.objects.all()), pk=request.data.get("event"))
        try:
            log = services.perform_checkin(
                event,
                serializer.validated_data["code"],
                action=serializer.validated_data["action"],
                actor=request.user,
                gate=serializer.validated_data.get("gate", ""),
                device=serializer.validated_data.get("device", ""),
                workshop=serializer.validated_data.get("workshop"),
                request=request,
            )
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(CheckInLogSerializer(log, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        workbook = services.export_participants_workbook(self.filter_queryset(self.get_queryset()))
        response = HttpResponse(
            services.workbook_bytes(workbook).getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="participants.xlsx"'
        return response


class PublicRegistrationAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PublicRegistrationSerializer, responses=ParticipantSerializer)
    def post(self, request, event_slug):
        event = get_object_or_404(Event, slug=event_slug, archived=False, is_deleted=False)
        serializer = PublicRegistrationSerializer(data=request.data, context={"event": event, "request": request})
        serializer.is_valid(raise_exception=True)
        try:
            participant = serializer.save()
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(ParticipantSerializer(participant, context={"request": request}).data, status=status.HTTP_201_CREATED)


class WorkshopViewSet(BaseScopedModelViewSet):
    queryset = Workshop.objects.select_related("event", "hall", "trainer").all()
    serializer_class = WorkshopSerializer
    search_fields = ["title", "description", "trainer__name", "hall__name"]
    filterset_fields = ["event", "hall", "trainer", "registration_open"]

    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        participant = get_object_or_404(scope_queryset(request.user, Participant.objects.all()), pk=request.data.get("participant"))
        try:
            registration = services.enroll_workshop(self.get_object(), participant, actor=request.user, request=request)
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(WorkshopRegistrationSerializer(registration, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def attend(self, request, pk=None):
        workshop = self.get_object()
        serializer = CheckInSerializer(data={**request.data, "action": CheckInLog.Action.WORKSHOP, "workshop": workshop.pk})
        serializer.is_valid(raise_exception=True)
        try:
            log = services.perform_checkin(
                workshop.event,
                serializer.validated_data["code"],
                action=CheckInLog.Action.WORKSHOP,
                actor=request.user,
                gate=serializer.validated_data.get("gate", ""),
                device=serializer.validated_data.get("device", ""),
                workshop=workshop,
                request=request,
            )
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(CheckInLogSerializer(log, context={"request": request}).data)


class CertificateViewSet(BaseScopedModelViewSet):
    queryset = Certificate.objects.select_related("event", "participant", "template").all()
    serializer_class = CertificateSerializer
    search_fields = ["serial_number", "verification_code", "participant__full_name", "event__name"]
    filterset_fields = ["event", "participant", "certificate_type", "status"]

    @action(detail=False, methods=["post"])
    def issue(self, request):
        participant = get_object_or_404(scope_queryset(request.user, Participant.objects.all()), pk=request.data.get("participant"))
        template = None
        if request.data.get("template"):
            template = get_object_or_404(CertificateTemplate, pk=request.data["template"], event=participant.event)
        try:
            certificate = services.issue_certificate(participant, actor=request.user, template=template, certificate_type=request.data.get("certificate_type", "attendance"))
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(CertificateSerializer(certificate, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        certificate = self.get_object()
        certificate.download_count += 1
        certificate.save(update_fields=["download_count", "updated_at"])
        return HttpResponse(services.render_certificate_pdf(certificate), content_type="application/pdf")

    @action(detail=True, methods=["post"])
    def send_email(self, request, pk=None):
        try:
            log = services.send_certificate_email(self.get_object())
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(EmailLogSerializer(log, context={"request": request}).data)


class BroadcastViewSet(BaseScopedModelViewSet):
    queryset = Broadcast.objects.select_related("event").all()
    serializer_class = BroadcastSerializer
    search_fields = ["title", "message", "audience"]
    filterset_fields = ["event", "channel", "status", "audience"]

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        broadcast = services.send_broadcast(self.get_object())
        return Response(self.get_serializer(broadcast).data)


class SOSReportViewSet(BaseScopedModelViewSet):
    queryset = SOSReport.objects.select_related("event", "reporter", "assigned_to").all()
    serializer_class = SOSReportSerializer
    search_fields = ["description", "location"]
    filterset_fields = ["event", "category", "priority", "status", "assigned_to"]

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        report = self.get_object()
        report.status = request.data.get("status", SOSReport.Status.CLOSED)
        report.resolution_notes = request.data.get("resolution_notes", report.resolution_notes)
        report.save()
        services.audit("sos.closed", report, actor=request.user, request=request, note=report.resolution_notes)
        return Response(self.get_serializer(report).data)


class SupportTicketViewSet(BaseScopedModelViewSet):
    queryset = SupportTicket.objects.select_related("event", "participant", "assigned_to").all()
    serializer_class = SupportTicketSerializer
    search_fields = ["tracking_code", "subject", "message", "participant__full_name"]
    filterset_fields = ["event", "status", "category", "priority", "assigned_to"]

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        ticket = self.get_object()
        reply = SupportReply.objects.create(
            ticket=ticket,
            author=request.user,
            message=request.data.get("message", ""),
            public=bool(request.data.get("public", True)),
        )
        if request.data.get("status"):
            ticket.status = request.data["status"]
            ticket.save(update_fields=["status", "updated_at"])
        services.audit("support.replied", reply, actor=request.user, request=request)
        return Response(SupportReplySerializer(reply, context={"request": request}).data, status=status.HTTP_201_CREATED)


class MobileMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        participant = Participant.objects.filter(user=request.user).select_related("event").first()
        return Response({
            "user": request.user.username,
            "role": getattr(request.user.profile, "role", ""),
            "participant": ParticipantSerializer(participant, context={"request": request}).data if participant else None,
        })


class MobileStudentDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        participant = Participant.objects.filter(user=request.user).select_related("event").first()
        if not participant and request.query_params.get("tracking_code"):
            participant = Participant.objects.filter(tracking_code=request.query_params["tracking_code"], is_deleted=False).select_related("event").first()
        if not participant:
            return Response({"participant": None, "detail": "No participant profile linked."})
        event = participant.event
        return Response({
            "participant": ParticipantSerializer(participant, context={"request": request}).data,
            "event": EventSerializer(event, context={"request": request}).data,
            "ticket": {
                "qr_code": participant.qr_code,
                "tracking_code": participant.tracking_code,
                "status": participant.status,
            },
            "sessions": SessionSerializer(event.sessions.filter(is_public=True)[:50], many=True, context={"request": request}).data,
            "workshops": WorkshopSerializer(event.workshops.all()[:50], many=True, context={"request": request}).data,
            "workshop_registrations": WorkshopRegistrationSerializer(participant.workshop_registrations.all(), many=True, context={"request": request}).data,
            "points_total": services.participant_points_total(participant),
            "badges": ParticipantBadgeSerializer(participant.badges.select_related("badge"), many=True, context={"request": request}).data,
            "certificates": CertificateSerializer(participant.certificates.all(), many=True, context={"request": request}).data,
            "support_tickets": SupportTicketSerializer(participant.supportticket_set.all() if hasattr(participant, "supportticket_set") else SupportTicket.objects.filter(participant=participant), many=True, context={"request": request}).data,
            "surveys": SurveySerializer(event.surveys.filter(active=True), many=True, context={"request": request}).data,
            "notifications": NotificationLogSerializer(NotificationLog.objects.filter(event=event, recipient_user=request.user)[:30], many=True, context={"request": request}).data,
        })


class MobileSupervisorDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        events = scope_queryset(request.user, Event.objects.all())
        return Response({
            "events": EventSerializer(events, many=True, context={"request": request}).data,
            "open_sos": SOSReportSerializer(scope_queryset(request.user, SOSReport.objects.exclude(status__in=[SOSReport.Status.CLOSED, SOSReport.Status.FALSE_ALARM]))[:50], many=True, context={"request": request}).data,
            "recent_checkins": CheckInLogSerializer(scope_queryset(request.user, CheckInLog.objects.select_related("event", "participant"))[:50], many=True, context={"request": request}).data,
            "violations": IncidentViolationSerializer(scope_queryset(request.user, IncidentViolation.objects.select_related("event", "participant"))[:50], many=True, context={"request": request}).data,
        })


class MobileVolunteerDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        participant = Participant.objects.filter(user=request.user).first()
        volunteer = Volunteer.objects.filter(participant=participant).select_related("participant", "participant__event").first() if participant else None
        if not volunteer:
            return Response({"volunteer": None, "detail": "No volunteer profile linked."})
        return Response({
            "volunteer": VolunteerSerializer(volunteer, context={"request": request}).data,
            "event": EventSerializer(volunteer.participant.event, context={"request": request}).data,
            "shifts": VolunteerShiftSerializer(volunteer.shifts.all(), many=True, context={"request": request}).data,
            "support_tickets": SupportTicketSerializer(SupportTicket.objects.filter(participant=volunteer.participant), many=True, context={"request": request}).data,
        })


class MobileAppVersionAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=AppVersionSerializer)
    def get(self, request):
        platform = request.query_params.get("platform", "android")
        version = AppVersion.objects.filter(platform=platform, active=True).first()
        return Response(AppVersionSerializer(version, context={"request": request}).data if version else {})


class MobileCheckInAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=CheckInSerializer, responses=CheckInLogSerializer)
    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(scope_queryset(request.user, Event.objects.all()), pk=request.data.get("event"))
        try:
            log = services.perform_checkin(
                event,
                serializer.validated_data["code"],
                action=serializer.validated_data["action"],
                actor=request.user,
                gate=serializer.validated_data.get("gate", "mobile"),
                device=serializer.validated_data.get("device", "mobile"),
                workshop=serializer.validated_data.get("workshop"),
                request=request,
            )
        except DjangoValidationError as exc:
            return api_error(exc)
        return Response(CheckInLogSerializer(log, context={"request": request}).data)


class ReadWriteSimpleViewSet(BaseScopedModelViewSet):
    pass


class UserProfileViewSet(ReadWriteSimpleViewSet):
    queryset = UserProfile.objects.select_related("user", "organization").all()
    serializer_class = UserProfileSerializer
    search_fields = ["user__username", "user__email", "phone"]
    filterset_fields = ["role", "organization"]


SIMPLE_VIEWSETS = {
    "event-days": (EventDay, EventDaySerializer),
    "tracks": (Track, TrackSerializer),
    "halls": (Hall, HallSerializer),
    "education-administrations": (EducationAdministration, EducationAdministrationSerializer),
    "schools": (School, SchoolSerializer),
    "groups": (ParticipantGroup, ParticipantGroupSerializer),
    "registration-forms": (RegistrationForm, RegistrationFormSerializer),
    "registration-fields": (RegistrationField, RegistrationFieldSerializer),
    "documents": (UploadedDocument, UploadedDocumentSerializer),
    "speakers": (Speaker, SpeakerSerializer),
    "sessions": (Session, SessionSerializer),
    "workshop-registrations": (WorkshopRegistration, WorkshopRegistrationSerializer),
    "checkin-logs": (CheckInLog, CheckInLogSerializer),
    "student-notes": (StudentNote, StudentNoteSerializer),
    "point-rules": (PointRule, PointRuleSerializer),
    "points": (PointTransaction, PointTransactionSerializer),
    "badges": (Badge, BadgeSerializer),
    "participant-badges": (ParticipantBadge, ParticipantBadgeSerializer),
    "violation-types": (ViolationType, ViolationTypeSerializer),
    "violations": (IncidentViolation, IncidentViolationSerializer),
    "certificate-templates": (CertificateTemplate, CertificateTemplateSerializer),
    "email-templates": (EmailTemplate, EmailTemplateSerializer),
    "email-logs": (EmailLog, EmailLogSerializer),
    "notification-logs": (NotificationLog, NotificationLogSerializer),
    "support-replies": (SupportReply, SupportReplySerializer),
    "volunteers": (Volunteer, VolunteerSerializer),
    "volunteer-shifts": (VolunteerShift, VolunteerShiftSerializer),
    "vip-invitations": (VIPInvitation, VIPInvitationSerializer),
    "sponsors": (Sponsor, SponsorSerializer),
    "media": (MediaItem, MediaItemSerializer),
    "surveys": (Survey, SurveySerializer),
    "survey-questions": (SurveyQuestion, SurveyQuestionSerializer),
    "survey-responses": (SurveyResponse, SurveyResponseSerializer),
    "ticket-types": (TicketType, TicketTypeSerializer),
    "coupons": (Coupon, CouponSerializer),
    "tickets": (Ticket, TicketSerializer),
    "invoices": (Invoice, InvoiceSerializer),
    "refunds": (Refund, RefundSerializer),
    "expenses": (Expense, ExpenseSerializer),
    "reports": (ReportSnapshot, ReportSnapshotSerializer),
    "app-versions": (AppVersion, AppVersionSerializer),
    "ai-insights": (AIInsight, AIInsightSerializer),
    "backups": (BackupJob, BackupJobSerializer),
    "subscription-plans": (SubscriptionPlan, SubscriptionPlanSerializer),
    "organization-subscriptions": (OrganizationSubscription, OrganizationSubscriptionSerializer),
    "audit-logs": (AuditLog, AuditLogSerializer),
}


FILTER_FIELD_TYPES = (
    django_models.AutoField,
    django_models.BigAutoField,
    django_models.IntegerField,
    django_models.BigIntegerField,
    django_models.PositiveIntegerField,
    django_models.PositiveSmallIntegerField,
    django_models.SmallIntegerField,
    django_models.BooleanField,
    django_models.CharField,
    django_models.EmailField,
    django_models.SlugField,
    django_models.DateField,
    django_models.DateTimeField,
    django_models.DecimalField,
    django_models.ForeignKey,
)

SEARCH_FIELD_TYPES = (
    django_models.CharField,
    django_models.TextField,
    django_models.EmailField,
    django_models.SlugField,
)


def model_filter_fields(model):
    return [
        field.name
        for field in model._meta.fields
        if isinstance(field, FILTER_FIELD_TYPES) and not isinstance(field, django_models.FileField)
    ]


def model_search_fields(model):
    return [
        field.name
        for field in model._meta.fields
        if isinstance(field, SEARCH_FIELD_TYPES) and not isinstance(field, django_models.FileField)
    ]


def build_simple_viewset(model, serializer):
    return type(
        f"{model.__name__}ViewSet",
        (ReadWriteSimpleViewSet,),
        {
            "queryset": model.objects.all(),
            "serializer_class": serializer,
            "filterset_fields": model_filter_fields(model),
            "search_fields": model_search_fields(model),
        },
    )


GENERATED_VIEWSETS = {name: build_simple_viewset(model, serializer) for name, (model, serializer) in SIMPLE_VIEWSETS.items()}
