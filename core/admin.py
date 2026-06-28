from django.contrib import admin

from . import models


class EventScopedAdmin(admin.ModelAdmin):
    list_per_page = 40


@admin.register(models.Organization)
class OrganizationAdmin(EventScopedAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug", "contact_email", "contact_phone")
    list_filter = ("is_active",)


@admin.register(models.Event)
class EventAdmin(EventScopedAdmin):
    list_display = ("name", "organization", "starts_at", "registration_open", "maintenance_mode", "archived")
    search_fields = ("name", "slug", "organization__name")
    list_filter = ("event_type", "registration_open", "maintenance_mode", "archived")


@admin.register(models.Participant)
class ParticipantAdmin(EventScopedAdmin):
    list_display = ("full_name", "event", "phone", "email", "registration_type", "status", "checked_in_at")
    search_fields = ("full_name", "phone", "email", "tracking_code", "qr_code")
    list_filter = ("status", "registration_type", "event")


@admin.register(models.CheckInLog)
class CheckInLogAdmin(EventScopedAdmin):
    list_display = ("event", "participant", "action", "success", "gate", "performed_by", "checked_at")
    search_fields = ("participant__full_name", "participant__tracking_code", "code_scanned", "gate")
    list_filter = ("action", "success", "event")


@admin.register(models.AuditLog)
class AuditLogAdmin(EventScopedAdmin):
    list_display = ("action", "entity_type", "entity_id", "actor", "event", "created_at")
    search_fields = ("action", "entity_type", "entity_id", "actor__username", "note")
    list_filter = ("action", "entity_type", "event")
    readonly_fields = ("created_at", "updated_at")


for model in [
    models.UserProfile,
    models.EventModule,
    models.EventDay,
    models.Track,
    models.Hall,
    models.EducationAdministration,
    models.School,
    models.ParticipantGroup,
    models.RegistrationForm,
    models.RegistrationField,
    models.UploadedDocument,
    models.Speaker,
    models.Session,
    models.Workshop,
    models.WorkshopRegistration,
    models.StudentNote,
    models.PointRule,
    models.PointTransaction,
    models.Badge,
    models.ParticipantBadge,
    models.ViolationType,
    models.IncidentViolation,
    models.CertificateTemplate,
    models.Certificate,
    models.EmailTemplate,
    models.EmailLog,
    models.NotificationLog,
    models.Broadcast,
    models.SOSReport,
    models.SupportTicket,
    models.SupportReply,
    models.Volunteer,
    models.VolunteerShift,
    models.VIPInvitation,
    models.Sponsor,
    models.MediaItem,
    models.Survey,
    models.SurveyQuestion,
    models.SurveyResponse,
    models.TicketType,
    models.Coupon,
    models.Ticket,
    models.Invoice,
    models.Refund,
    models.Expense,
    models.ReportSnapshot,
    models.AppVersion,
    models.AIInsight,
    models.BackupJob,
    models.SubscriptionPlan,
    models.OrganizationSubscription,
]:
    try:
        admin.site.register(model, EventScopedAdmin)
    except admin.sites.AlreadyRegistered:
        pass
