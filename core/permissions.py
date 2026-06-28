from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Event, Organization, Participant, Role, UserProfile


ROLE_CAPABILITIES = {
    Role.SUPER_ADMIN: {"*"},
    Role.ORGANIZATION_ADMIN: {"manage_org", "manage_event", "registrations", "checkin", "workshops", "certificates", "communications", "volunteers", "crisis", "finance", "media", "vip", "speakers", "sponsors", "support", "reports", "audit", "view"},
    Role.EVENT_MANAGER: {"manage_event", "registrations", "checkin", "workshops", "certificates", "communications", "volunteers", "crisis", "media", "vip", "speakers", "sponsors", "support", "reports", "view"},
    Role.REGISTRATION_MANAGER: {"registrations", "reports", "view"},
    Role.CHECKIN_STAFF: {"checkin", "view"},
    Role.WORKSHOP_MANAGER: {"workshops", "checkin", "view"},
    Role.CERTIFICATE_MANAGER: {"certificates", "reports", "view"},
    Role.COMMUNICATION_MANAGER: {"communications", "support", "view"},
    Role.VOLUNTEER_MANAGER: {"volunteers", "checkin", "view"},
    Role.CRISIS_MANAGER: {"crisis", "violations", "support", "view"},
    Role.FINANCE_MANAGER: {"finance", "reports", "view"},
    Role.MEDIA_MANAGER: {"media", "view"},
    Role.VIP_MANAGER: {"vip", "checkin", "view"},
    Role.SPEAKER_MANAGER: {"speakers", "workshops", "view"},
    Role.SPONSOR_MANAGER: {"sponsors", "reports", "view"},
    Role.SUPPORT_AGENT: {"support", "view"},
    Role.AUDITOR: {"audit", "reports", "view"},
    Role.VIEWER: {"view"},
    Role.MOBILE_STUDENT: {"mobile_student"},
    Role.MOBILE_SUPERVISOR: {"mobile_supervisor", "checkin", "crisis", "violations", "view"},
    Role.MOBILE_VOLUNTEER: {"mobile_volunteer", "support", "view"},
}

CAPABILITY_BY_METHOD = {
    "UserProfile": "manage_org",
    "Organization": "manage_org",
    "Event": "manage_event",
    "EventDay": "manage_event",
    "EventModule": "manage_event",
    "Track": "manage_event",
    "Hall": "manage_event",
    "Session": "manage_event",
    "EducationAdministration": "registrations",
    "School": "registrations",
    "ParticipantGroup": "registrations",
    "RegistrationForm": "registrations",
    "RegistrationField": "registrations",
    "Participant": "registrations",
    "UploadedDocument": "registrations",
    "CheckInLog": "checkin",
    "Workshop": "workshops",
    "WorkshopRegistration": "workshops",
    "PointRule": "manage_event",
    "PointTransaction": "manage_event",
    "Badge": "manage_event",
    "ParticipantBadge": "manage_event",
    "Certificate": "certificates",
    "CertificateTemplate": "certificates",
    "EmailTemplate": "communications",
    "EmailLog": "communications",
    "NotificationLog": "communications",
    "Broadcast": "communications",
    "SOSReport": "crisis",
    "SupportReply": "support",
    "ViolationType": "violations",
    "IncidentViolation": "violations",
    "Volunteer": "volunteers",
    "VolunteerShift": "volunteers",
    "StudentNote": "registrations",
    "VIPInvitation": "vip",
    "Speaker": "speakers",
    "Sponsor": "sponsors",
    "SupportTicket": "support",
    "MediaItem": "media",
    "Survey": "reports",
    "SurveyQuestion": "reports",
    "SurveyResponse": "reports",
    "Ticket": "finance",
    "TicketType": "finance",
    "Coupon": "finance",
    "Invoice": "finance",
    "Refund": "finance",
    "Expense": "finance",
    "ReportSnapshot": "reports",
    "AuditLog": "audit",
    "AIInsight": "reports",
    "AppVersion": "platform",
    "BackupJob": "platform",
    "SubscriptionPlan": "platform",
    "OrganizationSubscription": "platform",
}

SENSITIVE_READ_CAPABILITIES = {"audit", "finance", "manage_org", "platform"}


def user_profile(user):
    if not user or not user.is_authenticated:
        return None
    if hasattr(user, "profile"):
        return user.profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def has_capability(user, capability):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = user_profile(user)
    caps = ROLE_CAPABILITIES.get(profile.role, set()) if profile else set()
    return "*" in caps or capability in caps


def can_access_event(user, event):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = user_profile(user)
    if not profile:
        return False
    if profile.role == Role.SUPER_ADMIN:
        return True
    if profile.organization_id and event.organization_id == profile.organization_id:
        if profile.role == Role.ORGANIZATION_ADMIN:
            return True
        return profile.assigned_events.filter(pk=event.pk).exists() or has_capability(user, "manage_event")
    return profile.assigned_events.filter(pk=event.pk).exists()


def scope_queryset(user, queryset):
    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    profile = user_profile(user)
    if not profile or profile.role == Role.SUPER_ADMIN:
        return queryset
    model = queryset.model
    assigned_events = profile.assigned_events.all()
    field_names = {field.name for field in model._meta.get_fields()}
    if model is Organization:
        return queryset.filter(pk=profile.organization_id)
    if model is UserProfile:
        if profile.role == Role.ORGANIZATION_ADMIN and profile.organization_id:
            return queryset.filter(organization=profile.organization)
        return queryset.filter(user=user)
    if model is Event:
        base = queryset.filter(organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(pk__in=assigned_events.values("pk"))
    if "event" in field_names:
        base = queryset.filter(event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(event__in=assigned_events)
    if "participant" in field_names:
        base = queryset.filter(participant__event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(participant__event__in=assigned_events)
    if "workshop" in field_names:
        base = queryset.filter(workshop__event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(workshop__event__in=assigned_events)
    if "ticket" in field_names:
        base = queryset.filter(ticket__event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(ticket__event__in=assigned_events)
    if "volunteer" in field_names:
        base = queryset.filter(volunteer__participant__event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(volunteer__participant__event__in=assigned_events)
    if "survey" in field_names:
        base = queryset.filter(survey__event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(survey__event__in=assigned_events)
    if "organization" in field_names:
        return queryset.filter(organization=profile.organization)
    if model is Participant:
        base = queryset.filter(event__organization=profile.organization) if profile.organization_id else queryset.none()
        if profile.role == Role.ORGANIZATION_ADMIN:
            return base
        return base.filter(event__in=assigned_events)
    return queryset


class EventOSPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        model = getattr(getattr(view, "queryset", None), "model", None)
        capability = CAPABILITY_BY_METHOD.get(model.__name__ if model else "", "manage_event")
        if request.method in SAFE_METHODS:
            if capability in SENSITIVE_READ_CAPABILITIES:
                return has_capability(request.user, capability)
            return has_capability(request.user, capability) or has_capability(request.user, "view") or request.user.is_superuser
        return has_capability(request.user, capability)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        event = getattr(obj, "event", None)
        if isinstance(obj, Event):
            event = obj
        if event:
            return can_access_event(request.user, event)
        organization = getattr(obj, "organization", None)
        if organization:
            profile = user_profile(request.user)
            return request.user.is_superuser or profile.role == Role.SUPER_ADMIN or profile.organization_id == organization.id
        return True
