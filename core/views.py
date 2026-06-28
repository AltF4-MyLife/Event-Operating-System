from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import (
    AdminUserCreateForm,
    AppVersionForm,
    AwardBadgeForm,
    AwardPointsForm,
    BadgeForm,
    BackupJobForm,
    BroadcastForm,
    BulkCertificateIssueForm,
    BulkReviewForm,
    CertificateTemplateForm,
    CheckInForm,
    CouponForm,
    DirectParticipantEmailForm,
    EducationAdministrationForm,
    EmailTemplateForm,
    EventDayForm,
    EventForm,
    ExpenseForm,
    HallForm,
    IncidentViolationForm,
    InvoiceForm,
    MediaItemForm,
    OrganizationForm,
    OrganizationSubscriptionForm,
    ParticipantImportForm,
    ParticipantGroupForm,
    ParticipantUpdateForm,
    PointRuleForm,
    PushNotificationForm,
    PublicRegistrationForm,
    PublicSurveyResponseForm,
    RegistrationFieldForm,
    RegistrationFormSettingsForm,
    RefundForm,
    SOSReportForm,
    SchoolForm,
    SessionForm,
    SpeakerForm,
    SponsorForm,
    StudentNoteForm,
    SupportReplyForm,
    SupportTicketForm,
    SurveyForm,
    SurveyQuestionForm,
    SubscriptionPlanForm,
    TicketIssueForm,
    TicketTypeForm,
    TrackForm,
    UploadedDocumentForm,
    UserRoleUpdateForm,
    VIPInvitationForm,
    ViolationTypeForm,
    VolunteerForm,
    VolunteerShiftForm,
    WorkshopAttendanceForm,
    WorkshopForm,
)
from .models import (
    AppVersion,
    AuditLog,
    BackupJob,
    Badge,
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
    Hall,
    IncidentViolation,
    Invoice,
    MediaItem,
    ModuleCode,
    NotificationLog,
    Organization,
    OrganizationSubscription,
    Participant,
    ParticipantBadge,
    ParticipantGroup,
    PointRule,
    PointTransaction,
    RegistrationStatus,
    Refund,
    SOSReport,
    School,
    Session,
    Speaker,
    Sponsor,
    StudentNote,
    SupportReply,
    SupportTicket,
    Survey,
    SurveyQuestion,
    SurveyResponse,
    SubscriptionPlan,
    Ticket,
    TicketType,
    Expense,
    Track,
    UploadedDocument,
    Role,
    ReportSnapshot,
    UserProfile,
    VIPInvitation,
    ViolationType,
    Volunteer,
    VolunteerShift,
    Workshop,
    WorkshopRegistration,
)
from .permissions import can_access_event, has_capability, scope_queryset, user_profile


User = get_user_model()


def error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(exc.messages)
    return str(exc)


def public_home(request):
    events = Event.objects.filter(archived=False, is_deleted=False, organization__is_active=True).select_related("organization")[:12]
    featured = events[0] if events else None
    return render(request, "core/public_home.html", {"events": events, "featured": featured})


def public_event(request, slug):
    event = get_object_or_404(Event.objects.select_related("organization"), slug=slug, archived=False, is_deleted=False)
    services.ensure_default_modules(event)
    context = {
        "event": event,
        "speakers": event.speakers.filter(is_deleted=False, public_profile=True)[:8],
        "sponsors": event.sponsors.filter(show_on_site=True)[:12],
        "sessions": event.sessions.filter(is_public=True).select_related("hall", "track")[:8],
        "workshops": event.workshops.filter(registration_open=True).select_related("hall", "trainer")[:6],
        "leaderboard_enabled": event.module_enabled(ModuleCode.POINTS) or event.module_enabled(ModuleCode.BADGES),
    }
    return render(request, "core/public_event.html", context)


def public_register(request, slug):
    event = get_object_or_404(Event, slug=slug, archived=False, is_deleted=False)
    if event.maintenance_mode:
        return render(request, "core/maintenance.html", {"event": event})
    form = PublicRegistrationForm(request.POST or None, request.FILES or None, event=event)
    if request.method == "POST" and form.is_valid():
        try:
            participant = form.save(request=request)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"تم تسجيل الطلب بنجاح. رقم المتابعة: {participant.tracking_code}")
            return redirect("registration-status-code", slug=event.slug, code=participant.tracking_code)
    return render(request, "core/public_register.html", {"event": event, "form": form})


def registration_status(request, slug, code=None):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    code = code or request.GET.get("code", "")
    participant = None
    if code:
        participant = Participant.objects.filter(event=event, tracking_code=code, is_deleted=False).first()
        if not participant:
            messages.error(request, "لم يتم العثور على طلب بهذا الكود.")
    return render(request, "core/registration_status.html", {"event": event, "participant": participant, "code": code})


def ticket_view(request, slug, code):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    participant = get_object_or_404(Participant, event=event, tracking_code=code, is_deleted=False)
    if participant.status not in {RegistrationStatus.APPROVED, RegistrationStatus.CHECKED_IN, RegistrationStatus.CHECKED_OUT, RegistrationStatus.ATTENDED}:
        messages.error(request, "التذكرة تظهر للمقبولين فقط.")
        return redirect("registration-status-code", slug=slug, code=code)
    if request.GET.get("download") == "pdf":
        html = render_to_string("core/pdf_ticket.html", {"event": event, "participant": participant, "qr_image": services.qr_data_uri(participant.qr_code)})
        try:
            from weasyprint import HTML

            content = HTML(string=html).write_pdf()
        except Exception:
            content = html.encode("utf-8")
        return HttpResponse(content, content_type="application/pdf")
    return render(request, "core/ticket.html", {"event": event, "participant": participant, "qr_image": services.qr_data_uri(participant.qr_code)})


def schedule_view(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    day = request.GET.get("day")
    track = request.GET.get("track")
    hall = request.GET.get("hall")
    sessions = event.sessions.filter(is_public=True).select_related("day", "track", "hall").prefetch_related("speakers")
    if day:
        sessions = sessions.filter(day_id=day)
    if track:
        sessions = sessions.filter(track_id=track)
    if hall:
        sessions = sessions.filter(hall_id=hall)
    return render(request, "core/schedule.html", {"event": event, "sessions": sessions, "days": event.days.all(), "tracks": event.tracks.all(), "halls": event.halls.all()})


def workshops_view(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    workshops = event.workshops.select_related("trainer", "hall")
    if request.method == "POST":
        tracking_code = request.POST.get("tracking_code", "")
        workshop = get_object_or_404(Workshop, pk=request.POST.get("workshop"), event=event)
        participant = Participant.objects.filter(event=event, tracking_code=tracking_code, is_deleted=False).first()
        if not participant:
            messages.error(request, "كود المتابعة غير صحيح.")
        else:
            try:
                registration = services.enroll_workshop(workshop, participant, request=request)
                messages.success(request, f"تم تحديث حالة التسجيل في الورشة: {registration.get_status_display()}")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
        return redirect("public-workshops", slug=event.slug)
    return render(request, "core/workshops.html", {"event": event, "workshops": workshops})


def certificates_page(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    participant = None
    eligibility = None
    certificate = None
    code = request.GET.get("code") or request.POST.get("code")
    if code:
        participant = Participant.objects.filter(event=event, tracking_code=code, is_deleted=False).first()
        if participant:
            eligibility = services.certificate_eligibility(participant)
            if request.method == "POST" and eligibility[0]:
                try:
                    certificate = services.issue_certificate(participant)
                    messages.success(request, "تم إصدار الشهادة.")
                except ValidationError as exc:
                    messages.error(request, error_text(exc))
            else:
                certificate = participant.certificates.filter(status=Certificate.Status.ISSUED).first()
        else:
            messages.error(request, "كود المتابعة غير صحيح.")
    return render(request, "core/certificates.html", {"event": event, "participant": participant, "eligibility": eligibility, "certificate": certificate, "code": code})


def feedback_page(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    surveys = event.surveys.filter(active=True).prefetch_related("questions")
    survey = surveys.filter(pk=request.GET.get("survey")).first() if request.GET.get("survey") else surveys.first()
    form = PublicSurveyResponseForm(request.POST or None, survey=survey) if survey else None
    if request.method == "POST" and survey and form and form.is_valid():
        try:
            form.save()
            messages.success(request, "تم حفظ التقييم. شكرًا لمشاركتك.")
            return redirect("public-feedback", slug=event.slug)
        except ValidationError as exc:
            messages.error(request, error_text(exc))
    return render(request, "core/feedback.html", {"event": event, "surveys": surveys, "survey": survey, "form": form})


def media_center_page(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    items = event.media_items.filter(published=True).order_by("-created_at")
    return render(request, "core/media_center.html", {"event": event, "items": items})


def public_leaderboard(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    services.ensure_default_modules(event)
    if not (event.module_enabled(ModuleCode.POINTS) or event.module_enabled(ModuleCode.BADGES)):
        messages.error(request, "النقاط والأوسمة غير مفعلة لهذه الفعالية.")
        return redirect("public-event", slug=event.slug)
    participants = (
        event.participants.filter(
            is_deleted=False,
            status__in=[RegistrationStatus.APPROVED, RegistrationStatus.CHECKED_IN, RegistrationStatus.CHECKED_OUT, RegistrationStatus.ATTENDED],
        )
        .select_related("school", "education_administration", "group")
        .prefetch_related("badges__badge")
        .annotate(points_total=Sum("point_transactions__value", default=0))
        .order_by("-points_total", "full_name")[:100]
    )
    return render(request, "core/public_leaderboard.html", {"event": event, "participants": participants})


def certificate_verify(request, verification_code=None):
    verification_code = verification_code or request.GET.get("code", "")
    certificate = None
    if verification_code:
        certificate = Certificate.objects.filter(verification_code=verification_code).select_related("participant", "event", "event__organization").first()
        if not certificate:
            messages.error(request, "الشهادة غير موجودة.")
    return render(request, "core/certificate_verify.html", {"certificate": certificate, "verification_code": verification_code})


def certificate_pdf(request, verification_code):
    certificate = get_object_or_404(Certificate, verification_code=verification_code, status=Certificate.Status.ISSUED)
    certificate.download_count += 1
    certificate.save(update_fields=["download_count", "updated_at"])
    return HttpResponse(services.render_certificate_pdf(certificate), content_type="application/pdf")


def public_support(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    form = SupportTicketForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.event = event
        ticket.save()
        messages.success(request, f"تم فتح طلب الدعم. رقم المتابعة: {ticket.tracking_code}")
        return redirect("public-support", slug=event.slug)
    return render(request, "core/support.html", {"event": event, "form": form})


def public_support_status(request, slug, code=None):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    code = code or request.GET.get("code", "")
    ticket = None
    if code:
        ticket = SupportTicket.objects.filter(event=event, tracking_code=code).prefetch_related("replies").first()
        if not ticket:
            messages.error(request, "لم يتم العثور على طلب دعم بهذا الرقم.")
    return render(request, "core/support_status.html", {"event": event, "ticket": ticket, "code": code})


def public_display(request, slug):
    event = get_object_or_404(Event, slug=slug, is_deleted=False)
    now = timezone.now()
    context = {
        "event": event,
        "current_sessions": event.sessions.filter(starts_at__lte=now, ends_at__gte=now, is_public=True).select_related("hall"),
        "upcoming_sessions": event.sessions.filter(starts_at__gt=now, is_public=True).select_related("hall")[:8],
        "live_workshops": event.workshops.filter(starts_at__lte=now, ends_at__gte=now).select_related("hall")[:8],
        "checked_in": event.checkin_logs.filter(action=CheckInLog.Action.CHECKIN, success=True).values("participant_id").distinct().count(),
        "alerts": event.sos_reports.exclude(status__in=[SOSReport.Status.CLOSED, SOSReport.Status.FALSE_ALARM])[:5],
    }
    return render(request, "core/public_display.html", context)


def require_capability(user, capability):
    if not has_capability(user, capability):
        raise PermissionDenied


def require_super_admin(user):
    profile = user_profile(user)
    if not (user.is_superuser or (profile and profile.role == Role.SUPER_ADMIN)):
        raise PermissionDenied


def scoped_events(request):
    return scope_queryset(request.user, Event.objects.select_related("organization").filter(is_deleted=False))


def scoped_active_users(request):
    users = User.objects.filter(is_active=True).select_related("profile", "profile__organization")
    profile = user_profile(request.user)
    if profile and profile.organization_id and not request.user.is_superuser and profile.role != Role.SUPER_ADMIN:
        return users.filter(profile__organization=profile.organization)
    return users


@login_required
def dashboard(request):
    profile = user_profile(request.user)
    organization = profile.organization if profile and profile.organization_id and not request.user.is_superuser else None
    stats = services.dashboard_stats(organization=organization)
    events = scoped_events(request)[:8]
    recent_audit = scope_queryset(request.user, AuditLog.objects.select_related("actor", "event"))[:12]
    alerts = SOSReport.objects.filter(event__in=scoped_events(request)).exclude(status__in=[SOSReport.Status.CLOSED, SOSReport.Status.FALSE_ALARM])[:8]
    return render(request, "core/dashboard.html", {"stats": stats, "events": events, "recent_audit": recent_audit, "alerts": alerts})


@login_required
def organizations_admin(request):
    require_capability(request.user, "manage_org")
    organizations = scope_queryset(request.user, Organization.objects.filter(is_deleted=False))
    form = OrganizationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        organization = form.save()
        services.audit("organization.created", organization, actor=request.user, request=request)
        messages.success(request, "تم حفظ الجهة.")
        return redirect("admin-organizations")
    return render(request, "core/admin_organizations.html", {"organizations": organizations, "form": form})


@login_required
def events_admin(request):
    require_capability(request.user, "manage_event")
    events = scoped_events(request)
    form = EventForm(request.POST or None, request.FILES or None)
    profile = user_profile(request.user)
    if profile and profile.organization_id and not request.user.is_superuser:
        form.fields["organization"].queryset = Organization.objects.filter(pk=profile.organization_id)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        services.ensure_default_modules(event, actor=request.user)
        services.ensure_registration_form(event)
        services.audit("event.created", event, actor=request.user, request=request)
        messages.success(request, "تم حفظ الفعالية.")
        return redirect("admin-events")
    return render(request, "core/admin_events.html", {"events": events, "form": form})


@login_required
def users_admin(request):
    require_capability(request.user, "manage_org")
    profile = user_profile(request.user)
    organizations = Organization.objects.filter(is_deleted=False)
    if profile and profile.organization_id and not request.user.is_superuser and profile.role != Role.SUPER_ADMIN:
        organizations = organizations.filter(pk=profile.organization_id)
    events = scoped_events(request)
    users = User.objects.select_related("profile", "profile__organization").order_by("username")
    if profile and profile.organization_id and not request.user.is_superuser and profile.role != Role.SUPER_ADMIN:
        users = users.filter(profile__organization=profile.organization)
    create_form = AdminUserCreateForm(request.POST or None, organizations=organizations, events=events)
    if request.method == "POST":
        if request.POST.get("form_kind") == "create_user" and create_form.is_valid():
            user = create_form.save()
            services.audit("user.created", user.profile, actor=request.user, request=request, after={"username": user.username, "role": user.profile.role})
            messages.success(request, "تم إنشاء المستخدم.")
            return redirect("admin-users")
        if request.POST.get("form_kind") == "update_user":
            target = get_object_or_404(users, pk=request.POST.get("user"))
            update_form = UserRoleUpdateForm(request.POST, user=target, organizations=organizations, events=events)
            if update_form.is_valid():
                update_form.save()
                services.audit("user.role_updated", target.profile, actor=request.user, request=request, after={"role": target.profile.role})
                messages.success(request, "تم تحديث صلاحيات المستخدم.")
                return redirect("admin-users")
            messages.error(request, "تعذر تحديث المستخدم. راجع البيانات.")
    return render(request, "core/admin_users.html", {"users": users[:200], "create_form": create_form, "organizations": organizations, "events": events, "roles": Role.choices})


@login_required
def education_admin(request):
    require_capability(request.user, "registrations")
    profile = user_profile(request.user)
    organizations = Organization.objects.filter(is_deleted=False)
    if profile and profile.organization_id and not request.user.is_superuser and profile.role != Role.SUPER_ADMIN:
        organizations = organizations.filter(pk=profile.organization_id)
    administrations = EducationAdministration.objects.filter(organization__in=organizations)
    schools = School.objects.filter(administration__organization__in=organizations).select_related("administration")
    groups = scope_queryset(request.user, ParticipantGroup.objects.select_related("event", "supervisor"))
    admin_form = EducationAdministrationForm(request.POST or None, prefix="admin")
    school_form = SchoolForm(request.POST or None, prefix="school")
    group_form = ParticipantGroupForm(request.POST or None, prefix="group")
    admin_form.fields["organization"].queryset = organizations
    school_form.fields["administration"].queryset = administrations
    group_form.fields["event"].queryset = scoped_events(request)
    group_form.fields["supervisor"].queryset = User.objects.filter(profile__organization__in=organizations)
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "admin" and admin_form.is_valid():
            admin_form.save()
            messages.success(request, "تم حفظ الإدارة التعليمية.")
            return redirect("admin-education")
        if kind == "school" and school_form.is_valid():
            school_form.save()
            messages.success(request, "تم حفظ المدرسة.")
            return redirect("admin-education")
        if kind == "group" and group_form.is_valid():
            group_form.save()
            messages.success(request, "تم حفظ المجموعة.")
            return redirect("admin-education")
    return render(request, "core/admin_education.html", {"administrations": administrations[:100], "schools": schools[:150], "groups": groups[:100], "admin_form": admin_form, "school_form": school_form, "group_form": group_form})


def get_scoped_event_or_404(request, event_id):
    event = get_object_or_404(scoped_events(request), pk=event_id)
    if not can_access_event(request.user, event):
        raise Http404
    return event


@login_required
def event_modules_admin(request, event_id):
    require_capability(request.user, "manage_event")
    event = get_scoped_event_or_404(request, event_id)
    services.ensure_default_modules(event, actor=request.user)
    if request.method == "POST":
        module = get_object_or_404(EventModule, event=event, code=request.POST.get("code"))
        before = {"enabled": module.enabled}
        module.enabled = request.POST.get("enabled") == "on"
        module.changed_by = request.user
        module.save()
        services.audit("module.toggled", module, actor=request.user, before=before, after={"enabled": module.enabled}, request=request)
        messages.success(request, f"تم تحديث {module.get_code_display()}.")
        return redirect("admin-event-modules", event_id=event.id)
    return render(request, "core/admin_modules.html", {"event": event, "modules": event.modules.all()})


@login_required
def registration_form_admin(request, event_id):
    require_capability(request.user, "registrations")
    event = get_scoped_event_or_404(request, event_id)
    registration_form = services.ensure_registration_form(event)
    settings_form = RegistrationFormSettingsForm(request.POST or None, instance=registration_form, prefix="settings")
    field_form = RegistrationFieldForm(request.POST or None, prefix="field")
    if request.method == "POST":
        if request.POST.get("form_kind") == "settings" and settings_form.is_valid():
            settings_form.save()
            messages.success(request, "تم حفظ إعدادات النموذج.")
            return redirect("admin-registration-form", event_id=event.id)
        if request.POST.get("form_kind") == "field" and field_form.is_valid():
            field = field_form.save(commit=False)
            field.form = registration_form
            field.save()
            messages.success(request, "تم إضافة الحقل.")
            return redirect("admin-registration-form", event_id=event.id)
    return render(request, "core/admin_registration_form.html", {"event": event, "registration_form": registration_form, "settings_form": settings_form, "field_form": field_form})


@login_required
def venues_admin(request, event_id=None):
    require_capability(request.user, "manage_event")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    events = scoped_events(request)
    event_options = Event.objects.filter(pk=event.pk) if event else events
    days = scope_queryset(request.user, EventDay.objects.select_related("event"))
    tracks = scope_queryset(request.user, Track.objects.select_related("event"))
    halls = scope_queryset(request.user, Hall.objects.select_related("event", "responsible_user"))
    if event:
        days = days.filter(event=event)
        tracks = tracks.filter(event=event)
        halls = halls.filter(event=event)
    day_form = EventDayForm(request.POST or None, prefix="day")
    track_form = TrackForm(request.POST or None, prefix="track")
    hall_form = HallForm(request.POST or None, prefix="hall")
    for form in [day_form, track_form, hall_form]:
        form.fields["event"].queryset = event_options
    hall_form.fields["responsible_user"].queryset = scoped_active_users(request)
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        form = {"day": day_form, "track": track_form, "hall": hall_form}.get(kind)
        if form and form.is_valid():
            item = form.save()
            services.audit(f"venue.{kind}.saved", item, actor=request.user, request=request)
            messages.success(request, "تم حفظ بيانات المكان.")
            return redirect(request.path)
    return render(
        request,
        "core/admin_venues.html",
        {"event": event, "day_form": day_form, "track_form": track_form, "hall_form": hall_form, "days": days[:100], "tracks": tracks[:100], "halls": halls[:150]},
    )


@login_required
def sessions_admin(request, event_id=None):
    require_capability(request.user, "manage_event")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    events = scoped_events(request)
    event_options = Event.objects.filter(pk=event.pk) if event else events
    sessions = scope_queryset(request.user, Session.objects.select_related("event", "day", "track", "hall").prefetch_related("speakers"))
    days = scope_queryset(request.user, EventDay.objects.select_related("event"))
    tracks = scope_queryset(request.user, Track.objects.select_related("event"))
    halls = scope_queryset(request.user, Hall.objects.select_related("event"))
    speakers = scope_queryset(request.user, Speaker.objects.select_related("event").filter(is_deleted=False))
    if event:
        sessions = sessions.filter(event=event)
        days = days.filter(event=event)
        tracks = tracks.filter(event=event)
        halls = halls.filter(event=event)
        speakers = speakers.filter(event=event)
    form = SessionForm(request.POST or None)
    form.fields["event"].queryset = event_options
    form.fields["day"].queryset = days
    form.fields["track"].queryset = tracks
    form.fields["hall"].queryset = halls
    form.fields["speakers"].queryset = speakers
    if request.method == "POST" and form.is_valid():
        session = form.save()
        services.audit("session.saved", session, actor=request.user, request=request)
        messages.success(request, "تم حفظ الجلسة.")
        return redirect(request.path)
    return render(request, "core/admin_sessions.html", {"event": event, "form": form, "sessions": sessions[:200]})


@login_required
def volunteers_admin(request, event_id=None):
    require_capability(request.user, "volunteers")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    participants = scope_queryset(
        request.user,
        Participant.objects.filter(is_deleted=False, registration_type=Participant.RegistrationType.VOLUNTEER, volunteer_profile__isnull=True).select_related("event"),
    )
    volunteers = scope_queryset(request.user, Volunteer.objects.select_related("participant", "participant__event"))
    shifts = scope_queryset(request.user, VolunteerShift.objects.select_related("volunteer", "volunteer__participant", "volunteer__participant__event"))
    if event:
        participants = participants.filter(event=event)
        volunteers = volunteers.filter(participant__event=event)
        shifts = shifts.filter(volunteer__participant__event=event)
    volunteer_form = VolunteerForm(request.POST or None, prefix="volunteer")
    shift_form = VolunteerShiftForm(request.POST or None, prefix="shift")
    volunteer_form.fields["participant"].queryset = participants
    shift_form.fields["volunteer"].queryset = volunteers
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "volunteer" and volunteer_form.is_valid():
            volunteer = volunteer_form.save()
            services.audit("volunteer.saved", volunteer, actor=request.user, request=request)
            messages.success(request, "تم حفظ المتطوع.")
            return redirect(request.path)
        if kind == "shift" and shift_form.is_valid():
            shift = shift_form.save()
            services.audit("volunteer_shift.saved", shift, actor=request.user, request=request)
            messages.success(request, "تم حفظ الشيفت.")
            return redirect(request.path)
    return render(request, "core/admin_volunteers.html", {"event": event, "volunteer_form": volunteer_form, "shift_form": shift_form, "volunteers": volunteers[:150], "shifts": shifts[:150]})


@login_required
def student_notes_admin(request, event_id=None):
    if not any(has_capability(request.user, capability) for capability in ["registrations", "workshops", "manage_event"]):
        raise PermissionDenied
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    participants = scope_queryset(request.user, Participant.objects.filter(is_deleted=False).select_related("event"))
    sessions = scope_queryset(request.user, Session.objects.select_related("event"))
    workshops = scope_queryset(request.user, Workshop.objects.select_related("event"))
    notes = scope_queryset(request.user, StudentNote.objects.select_related("participant", "participant__event", "author", "session", "workshop"))
    if event:
        participants = participants.filter(event=event)
        sessions = sessions.filter(event=event)
        workshops = workshops.filter(event=event)
        notes = notes.filter(participant__event=event)
    form = StudentNoteForm(request.POST or None)
    form.fields["participant"].queryset = participants
    form.fields["session"].queryset = sessions
    form.fields["workshop"].queryset = workshops
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        note.author = request.user
        note.save()
        services.audit("student_note.saved", note, actor=request.user, request=request)
        messages.success(request, "تم حفظ الملاحظة.")
        return redirect(request.path)
    return render(request, "core/admin_student_notes.html", {"event": event, "form": form, "notes": notes[:200]})


@login_required
def gamification_admin(request, event_id=None):
    require_capability(request.user, "manage_event")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    events = scoped_events(request)
    event_options = Event.objects.filter(pk=event.pk) if event else events
    participants = scope_queryset(
        request.user,
        Participant.objects.filter(is_deleted=False).select_related("event", "school", "education_administration", "group").prefetch_related("badges__badge"),
    )
    rules = scope_queryset(request.user, PointRule.objects.select_related("event"))
    badges = scope_queryset(request.user, Badge.objects.select_related("event"))
    transactions = scope_queryset(request.user, PointTransaction.objects.select_related("participant", "participant__event", "awarded_by"))
    badge_awards = scope_queryset(request.user, ParticipantBadge.objects.select_related("participant", "participant__event", "badge", "awarded_by"))
    if event:
        participants = participants.filter(event=event)
        rules = rules.filter(event=event)
        badges = badges.filter(event=event)
        transactions = transactions.filter(participant__event=event)
        badge_awards = badge_awards.filter(participant__event=event)

    rule_form = PointRuleForm(request.POST or None, prefix="rule")
    badge_form = BadgeForm(request.POST or None, prefix="badge")
    points_form = AwardPointsForm(request.POST or None, prefix="points", events=event_options, participants=participants)
    award_badge_form = AwardBadgeForm(request.POST or None, prefix="award_badge", events=event_options, participants=participants, badges=badges)
    for form in [rule_form, badge_form]:
        form.fields["event"].queryset = event_options

    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "rule" and rule_form.is_valid():
            rule = rule_form.save()
            services.audit("point_rule.saved", rule, actor=request.user, request=request)
            messages.success(request, "تم حفظ قاعدة النقاط.")
            return redirect(request.path)
        if kind == "badge" and badge_form.is_valid():
            badge = badge_form.save()
            if badge.auto_award:
                for participant in participants.filter(event=badge.event):
                    services.apply_auto_badges(participant, actor=request.user)
            services.audit("badge.saved", badge, actor=request.user, request=request)
            messages.success(request, "تم حفظ الوسام.")
            return redirect(request.path)
        if kind == "points" and points_form.is_valid():
            transaction = points_form.save(actor=request.user)
            services.audit("points.manual_award", transaction, actor=request.user, request=request)
            messages.success(request, "تم تسجيل حركة النقاط.")
            return redirect(request.path)
        if kind == "award_badge" and award_badge_form.is_valid():
            award = award_badge_form.save(actor=request.user)
            services.audit("badge.manual_award", award, actor=request.user, request=request)
            messages.success(request, "تم منح الوسام.")
            return redirect(request.path)

    leaderboard = participants.annotate(points_total=Sum("point_transactions__value", default=0)).order_by("-points_total", "full_name")[:30]
    volunteer_leaderboard = (
        participants.filter(registration_type=Participant.RegistrationType.VOLUNTEER)
        .annotate(points_total=Sum("point_transactions__value", default=0))
        .order_by("-points_total", "full_name")[:20]
    )
    school_board = participants.exclude(school__isnull=True).values("school__name").annotate(total=Count("id", distinct=True), points_total=Sum("point_transactions__value", default=0)).order_by("-points_total")[:10]
    administration_board = (
        participants.exclude(education_administration__isnull=True)
        .values("education_administration__name")
        .annotate(total=Count("id", distinct=True), points_total=Sum("point_transactions__value", default=0))
        .order_by("-points_total")[:10]
    )
    group_board = participants.exclude(group__isnull=True).values("group__name").annotate(total=Count("id", distinct=True), points_total=Sum("point_transactions__value", default=0)).order_by("-points_total")[:10]
    total_points = transactions.aggregate(total=Sum("value")).get("total") or 0
    context = {
        "event": event,
        "events": events,
        "rule_form": rule_form,
        "badge_form": badge_form,
        "points_form": points_form,
        "award_badge_form": award_badge_form,
        "rules": rules[:100],
        "badges": badges[:100],
        "transactions": transactions[:100],
        "badge_awards": badge_awards[:100],
        "leaderboard": leaderboard,
        "volunteer_leaderboard": volunteer_leaderboard,
        "school_board": school_board,
        "administration_board": administration_board,
        "group_board": group_board,
        "total_points": total_points,
    }
    return render(request, "core/admin_gamification.html", context)


@login_required
def registrations_admin(request, event_id=None):
    require_capability(request.user, "registrations")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    queryset = scope_queryset(request.user, Participant.objects.select_related("event", "school", "education_administration").filter(is_deleted=False))
    if event:
        queryset = queryset.filter(event=event)
    search = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")
    if search:
        queryset = queryset.filter(Q(full_name__icontains=search) | Q(phone__icontains=search) | Q(email__icontains=search) | Q(tracking_code__icontains=search))
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    import_form = ParticipantImportForm(request.POST or None, request.FILES or None, prefix="import")
    bulk_form = BulkReviewForm(request.POST or None, prefix="bulk")
    if request.method == "POST":
        form_kind = request.POST.get("form_kind", "single")
        if form_kind == "import":
            if not event:
                messages.error(request, "اختر فعالية محددة قبل الاستيراد.")
            elif import_form.is_valid():
                try:
                    result = services.import_participants_workbook(
                        event,
                        import_form.cleaned_data["file"],
                        actor=request.user,
                        request=request,
                        default_status=import_form.cleaned_data["default_status"],
                    )
                    messages.success(request, f"تم استيراد {result['created']} مشارك، وتخطي {result['skipped']}.")
                    if result["errors"]:
                        messages.error(request, f"أول خطأ: صف {result['errors'][0]['row']} - {result['errors'][0]['error']}")
                except ValidationError as exc:
                    messages.error(request, error_text(exc))
        elif form_kind == "bulk":
            selected = request.POST.getlist("selected")
            selected_queryset = queryset.filter(pk__in=selected)
            if not selected:
                messages.error(request, "حدد مشاركين أولًا.")
            elif bulk_form.is_valid():
                try:
                    count = services.bulk_review_participants(
                        selected_queryset,
                        bulk_form.cleaned_data["action"],
                        actor=request.user,
                        note=bulk_form.cleaned_data["note"],
                        request=request,
                    )
                    messages.success(request, f"تم تطبيق الإجراء على {count} مشارك.")
                except ValidationError as exc:
                    messages.error(request, error_text(exc))
        else:
            participant = get_object_or_404(queryset, pk=request.POST.get("participant"))
            try:
                services.review_participant(participant, request.POST.get("action"), actor=request.user, note=request.POST.get("note", ""), request=request)
                messages.success(request, "تم تحديث حالة الطلب.")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
        return redirect(request.path)
    return render(
        request,
        "core/admin_registrations.html",
        {
            "event": event,
            "participants": queryset[:200],
            "statuses": RegistrationStatus.choices,
            "search": search,
            "status_filter": status_filter,
            "import_form": import_form,
            "bulk_form": bulk_form,
        },
    )


@login_required
def participant_detail_admin(request, participant_id):
    if not any(has_capability(request.user, capability) for capability in ["registrations", "manage_event", "reports"]):
        raise PermissionDenied
    participant = get_object_or_404(
        scope_queryset(
            request.user,
            Participant.objects.select_related("event", "event__organization", "school", "education_administration", "group", "user").filter(is_deleted=False),
        ),
        pk=participant_id,
    )
    event = participant.event
    update_form = ParticipantUpdateForm(request.POST or None, instance=participant, prefix="participant")
    note_form = StudentNoteForm(request.POST or None, prefix="note")
    document_form = UploadedDocumentForm(request.POST or None, request.FILES or None, prefix="document")
    points_form = AwardPointsForm(
        request.POST or None,
        prefix="points",
        events=Event.objects.filter(pk=event.pk),
        participants=Participant.objects.filter(pk=participant.pk),
    )

    update_form.fields["school"].queryset = School.objects.filter(administration__organization=event.organization, is_active=True)
    update_form.fields["education_administration"].queryset = EducationAdministration.objects.filter(organization=event.organization)
    update_form.fields["group"].queryset = ParticipantGroup.objects.filter(event=event)
    note_form.fields["participant"].queryset = Participant.objects.filter(pk=participant.pk)
    note_form.fields["participant"].initial = participant.pk
    note_form.fields["session"].queryset = event.sessions.all()
    note_form.fields["workshop"].queryset = event.workshops.all()
    points_form.fields["event"].initial = event.pk
    points_form.fields["participant"].initial = participant.pk

    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "update" and update_form.is_valid():
            before = {"status": participant.status, "phone": participant.phone, "email": participant.email}
            updated = update_form.save()
            services.audit("participant.updated", updated, actor=request.user, request=request, before=before, after={"status": updated.status, "phone": updated.phone, "email": updated.email})
            messages.success(request, "تم تحديث بيانات المشارك.")
            return redirect("admin-participant-detail", participant_id=participant.id)
        if kind == "review":
            try:
                services.review_participant(participant, request.POST.get("action"), actor=request.user, note=request.POST.get("note", ""), request=request)
                messages.success(request, "تم تحديث حالة المشارك.")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
            return redirect("admin-participant-detail", participant_id=participant.id)
        if kind == "note" and note_form.is_valid():
            note = note_form.save(commit=False)
            note.participant = participant
            note.author = request.user
            note.save()
            services.audit("student_note.saved", note, actor=request.user, request=request)
            messages.success(request, "تم حفظ الملاحظة.")
            return redirect("admin-participant-detail", participant_id=participant.id)
        if kind == "document" and document_form.is_valid():
            document = document_form.save(commit=False)
            document.participant = participant
            document.save()
            services.audit("participant_document.saved", document, actor=request.user, request=request)
            messages.success(request, "تم حفظ المستند.")
            return redirect("admin-participant-detail", participant_id=participant.id)
        if kind == "points" and points_form.is_valid():
            tx = points_form.save(actor=request.user)
            services.audit("points.manual_award", tx, actor=request.user, request=request)
            messages.success(request, "تم تسجيل النقاط.")
            return redirect("admin-participant-detail", participant_id=participant.id)
        if kind == "issue_certificate":
            try:
                certificate = services.issue_certificate(participant, actor=request.user)
                messages.success(request, f"تم إصدار الشهادة: {certificate.serial_number}")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
            return redirect("admin-participant-detail", participant_id=participant.id)

    context = {
        "participant": participant,
        "event": event,
        "update_form": update_form,
        "note_form": note_form,
        "document_form": document_form,
        "points_form": points_form,
        "documents": participant.documents.all(),
        "notes": participant.notes.select_related("author", "session", "workshop")[:50],
        "checkins": participant.checkin_logs.select_related("workshop", "performed_by")[:50],
        "workshop_registrations": participant.workshop_registrations.select_related("workshop", "workshop__hall")[:50],
        "point_transactions": participant.point_transactions.select_related("awarded_by")[:50],
        "badges": participant.badges.select_related("badge", "awarded_by")[:50],
        "certificates": participant.certificates.select_related("template")[:50],
        "violations": participant.violations.select_related("violation_type", "reported_by")[:50],
        "support_tickets": SupportTicket.objects.filter(participant=participant)[:50],
        "audit_logs": AuditLog.objects.filter(entity_type="Participant", entity_id=str(participant.pk))[:30],
        "points_total": services.participant_points_total(participant),
        "attendance_percent": services.attendance_percent(participant),
    }
    return render(request, "core/admin_participant_detail.html", context)


@login_required
def export_participants(request, event_id=None):
    require_capability(request.user, "reports")
    queryset = scope_queryset(request.user, Participant.objects.select_related("event").filter(is_deleted=False))
    if event_id:
        queryset = queryset.filter(event=get_scoped_event_or_404(request, event_id))
    response = excel_response(services.export_participants_workbook(queryset), "participants.xlsx")
    return response


def excel_response(workbook, filename):
    response = HttpResponse(services.workbook_bytes(workbook).getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_attendance(request, event_id=None):
    require_capability(request.user, "reports")
    queryset = scope_queryset(request.user, CheckInLog.objects.select_related("event", "participant", "performed_by"))
    if event_id:
        queryset = queryset.filter(event=get_scoped_event_or_404(request, event_id))
    return excel_response(services.export_attendance_workbook(queryset), "attendance.xlsx")


@login_required
def export_certificates_report(request, event_id=None):
    require_capability(request.user, "reports")
    queryset = scope_queryset(request.user, Certificate.objects.select_related("event", "participant"))
    if event_id:
        queryset = queryset.filter(event=get_scoped_event_or_404(request, event_id))
    return excel_response(services.export_certificates_workbook(queryset), "certificates.xlsx")


@login_required
def export_workshops_report(request, event_id=None):
    require_capability(request.user, "reports")
    queryset = scope_queryset(request.user, Workshop.objects.select_related("event", "trainer", "hall"))
    if event_id:
        queryset = queryset.filter(event=get_scoped_event_or_404(request, event_id))
    return excel_response(services.export_workshops_workbook(queryset), "workshops.xlsx")


@login_required
def export_violations_report(request, event_id=None):
    require_capability(request.user, "reports")
    queryset = scope_queryset(request.user, IncidentViolation.objects.select_related("event", "participant", "violation_type", "reported_by"))
    if event_id:
        queryset = queryset.filter(event=get_scoped_event_or_404(request, event_id))
    return excel_response(services.export_violations_workbook(queryset), "violations.xlsx")


@login_required
def checkin_admin(request, event_id):
    require_capability(request.user, "checkin")
    event = get_scoped_event_or_404(request, event_id)
    form = CheckInForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.perform_checkin(
                event,
                form.cleaned_data["code"],
                action=form.cleaned_data["action"],
                actor=request.user,
                gate=form.cleaned_data["gate"],
                device=form.cleaned_data["device"],
                request=request,
            )
            messages.success(request, "تم تسجيل الإجراء بنجاح.")
        except ValidationError as exc:
            messages.error(request, error_text(exc))
        return redirect("admin-checkin", event_id=event.id)
    logs = event.checkin_logs.select_related("participant", "performed_by")[:50]
    return render(request, "core/admin_checkin.html", {"event": event, "form": form, "logs": logs})


@login_required
def workshops_admin(request, event_id=None):
    require_capability(request.user, "workshops")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    workshops = scope_queryset(request.user, Workshop.objects.select_related("event", "trainer", "hall"))
    if event:
        workshops = workshops.filter(event=event)
    form = WorkshopForm(request.POST or None)
    attendance_form = WorkshopAttendanceForm(request.POST or None, event=event)
    if event:
        form.fields["event"].queryset = Event.objects.filter(pk=event.pk)
    if request.method == "POST":
        if request.POST.get("form_kind") == "attendance":
            if attendance_form.is_valid():
                workshop = attendance_form.cleaned_data["workshop"]
                try:
                    services.perform_checkin(
                        workshop.event,
                        attendance_form.cleaned_data["code"],
                        action=CheckInLog.Action.WORKSHOP,
                        actor=request.user,
                        gate=attendance_form.cleaned_data["gate"] or (workshop.hall.name if workshop.hall else ""),
                        device=attendance_form.cleaned_data["device"],
                        workshop=workshop,
                        request=request,
                    )
                    messages.success(request, "تم تسجيل حضور الورشة ومنح النقاط عند وجودها.")
                except ValidationError as exc:
                    messages.error(request, error_text(exc))
            return redirect(request.path)
        if form.is_valid():
            workshop = form.save()
            services.audit("workshop.saved", workshop, actor=request.user, request=request)
            messages.success(request, "تم حفظ الورشة.")
            return redirect(request.path)
        return redirect(request.path)
    return render(request, "core/admin_workshops.html", {"event": event, "workshops": workshops, "form": form, "attendance_form": attendance_form})


@login_required
def certificates_admin(request, event_id=None):
    require_capability(request.user, "certificates")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    events = scoped_events(request)
    event_options = Event.objects.filter(pk=event.pk) if event else events
    certificates = scope_queryset(request.user, Certificate.objects.select_related("event", "participant", "template"))
    if event:
        certificates = certificates.filter(event=event)
    template_form = CertificateTemplateForm(request.POST or None, prefix="template")
    bulk_form = BulkCertificateIssueForm(request.POST or None, prefix="bulk", events=event_options)
    template_form.fields["event"].queryset = event_options
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "template" and template_form.is_valid():
            template_form.save()
            messages.success(request, "تم حفظ قالب الشهادة.")
            return redirect(request.path)
        if kind == "bulk_issue" and bulk_form.is_valid():
            target_event = bulk_form.cleaned_data["event"]
            statuses = bulk_form.cleaned_data.get("statuses") or [RegistrationStatus.APPROVED, RegistrationStatus.CHECKED_IN, RegistrationStatus.CHECKED_OUT, RegistrationStatus.ATTENDED]
            participants = scope_queryset(request.user, Participant.objects.filter(event=target_event, is_deleted=False, status__in=statuses))
            issued = 0
            emailed = 0
            skipped = 0
            for participant in participants:
                try:
                    certificate = services.issue_certificate(participant, actor=request.user, certificate_type=bulk_form.cleaned_data["certificate_type"])
                    issued += 1
                    if bulk_form.cleaned_data.get("send_email") and participant.email:
                        services.send_certificate_email(certificate)
                        emailed += 1
                except ValidationError:
                    skipped += 1
            messages.success(request, f"تم إصدار/تحديث {issued} شهادة، وإرسال {emailed} بريد، وتخطي {skipped}.")
            return redirect(request.path)
        if kind == "bulk_send" and bulk_form.is_valid():
            target_event = bulk_form.cleaned_data["event"]
            issued_certificates = scope_queryset(request.user, Certificate.objects.select_related("event", "participant")).filter(event=target_event, status=Certificate.Status.ISSUED)
            sent = 0
            skipped = 0
            for certificate in issued_certificates:
                try:
                    services.send_certificate_email(certificate)
                    sent += 1
                except ValidationError:
                    skipped += 1
            messages.success(request, f"تم تسجيل إرسال {sent} شهادة، وتخطي {skipped}.")
            return redirect(request.path)
        if kind == "send_email":
            certificate = get_object_or_404(certificates, pk=request.POST.get("certificate"))
            try:
                log = services.send_certificate_email(certificate)
                messages.success(request, f"تم تسجيل محاولة الإرسال: {log.get_status_display()}")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
            return redirect(request.path)
        if kind == "cancel_certificate":
            certificate = get_object_or_404(certificates, pk=request.POST.get("certificate"))
            certificate.status = Certificate.Status.CANCELLED
            certificate.save(update_fields=["status", "updated_at"])
            services.audit("certificate.cancelled", certificate, actor=request.user, request=request)
            messages.success(request, "تم إلغاء الشهادة.")
            return redirect(request.path)
        if kind == "reissue_certificate":
            certificate = get_object_or_404(certificates, pk=request.POST.get("certificate"))
            try:
                reissued = services.issue_certificate(certificate.participant, actor=request.user, template=certificate.template, certificate_type=certificate.certificate_type)
                messages.success(request, f"تمت إعادة إصدار الشهادة: {reissued.serial_number}")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
            return redirect(request.path)
        participant = Participant.objects.filter(tracking_code=request.POST.get("tracking_code"), event__in=scoped_events(request)).first()
        if event and participant and participant.event_id != event.id:
            participant = None
        if not participant:
            messages.error(request, "كود المشارك غير صحيح.")
        else:
            try:
                certificate = services.issue_certificate(participant, actor=request.user)
                messages.success(request, f"تم إصدار الشهادة: {certificate.serial_number}")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
        return redirect(request.path)
    return render(request, "core/admin_certificates.html", {"event": event, "certificates": certificates[:200], "template_form": template_form, "bulk_form": bulk_form})


@login_required
def communications_admin(request):
    require_capability(request.user, "communications")
    events = scoped_events(request)
    participants = scope_queryset(request.user, Participant.objects.filter(is_deleted=False).exclude(email="").select_related("event"))
    broadcasts = scope_queryset(request.user, Broadcast.objects.select_related("event"))[:100]
    templates = scope_queryset(request.user, EmailTemplate.objects.select_related("event"))
    email_logs = scope_queryset(request.user, EmailLog.objects.select_related("event", "participant"))[:120]
    notification_logs = scope_queryset(request.user, NotificationLog.objects.select_related("event", "recipient_user"))[:120]
    broadcast_form = BroadcastForm(request.POST or None, prefix="broadcast")
    template_form = EmailTemplateForm(request.POST or None, prefix="template")
    email_form = DirectParticipantEmailForm(request.POST or None, prefix="email", events=events, participants=participants, templates=templates)
    push_form = PushNotificationForm(request.POST or None, prefix="push", events=events)
    broadcast_form.fields["event"].queryset = events
    template_form.fields["event"].queryset = events
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "broadcast" and broadcast_form.is_valid():
            broadcast = broadcast_form.save(commit=False)
            broadcast.created_by = request.user
            broadcast.save()
            if "send_now" in request.POST:
                services.send_broadcast(broadcast)
            services.audit("broadcast.saved", broadcast, actor=request.user, request=request)
            messages.success(request, "تم حفظ الرسالة.")
            return redirect("admin-communications")
        if kind == "template" and template_form.is_valid():
            template = template_form.save()
            services.audit("email_template.saved", template, actor=request.user, request=request)
            messages.success(request, "تم حفظ قالب البريد.")
            return redirect("admin-communications")
        if kind == "email" and email_form.is_valid():
            log = email_form.save(actor=request.user)
            messages.success(request, f"تم تسجيل إرسال البريد: {log.get_status_display()}.")
            return redirect("admin-communications")
        if kind == "push" and push_form.is_valid():
            log = push_form.save()
            services.audit("push.sent", log, actor=request.user, request=request)
            messages.success(request, "تم تسجيل الإشعار.")
            return redirect("admin-communications")
        if kind == "resend_email":
            log = get_object_or_404(scope_queryset(request.user, EmailLog.objects.select_related("event", "participant")), pk=request.POST.get("email_log"))
            resent = services.send_event_email(log.event, log.to_email, log.subject, log.body, participant=log.participant)
            services.audit("email.resent", resent, actor=request.user, request=request)
            messages.success(request, f"تمت إعادة الإرسال كعملية جديدة: {resent.get_status_display()}.")
            return redirect("admin-communications")
    return render(
        request,
        "core/admin_communications.html",
        {
            "broadcasts": broadcasts,
            "templates": templates[:100],
            "email_logs": email_logs,
            "notification_logs": notification_logs,
            "broadcast_form": broadcast_form,
            "template_form": template_form,
            "email_form": email_form,
            "push_form": push_form,
        },
    )


@login_required
def crisis_admin(request):
    require_capability(request.user, "crisis")
    reports = scope_queryset(request.user, SOSReport.objects.select_related("event", "reporter", "assigned_to"))[:150]
    form = SOSReportForm(request.POST or None)
    form.fields["event"].queryset = scoped_events(request)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.reporter = request.user
        report.save()
        messages.success(request, "تم حفظ البلاغ.")
        return redirect("admin-crisis")
    return render(request, "core/admin_crisis.html", {"reports": reports, "form": form})


@login_required
def support_admin(request):
    require_capability(request.user, "support")
    tickets = scope_queryset(request.user, SupportTicket.objects.select_related("event", "participant", "assigned_to"))[:150]
    reply_form = SupportReplyForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        ticket = get_object_or_404(tickets, pk=request.POST.get("ticket"))
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.ticket = ticket
            reply.author = request.user
            reply.save()
            if request.POST.get("status"):
                ticket.status = request.POST["status"]
                ticket.save(update_fields=["status", "updated_at"])
            messages.success(request, "تم إرسال الرد.")
            return redirect("admin-support")
    return render(request, "core/admin_support.html", {"tickets": tickets, "reply_form": reply_form})


@login_required
def people_admin(request):
    require_capability(request.user, "vip")
    vip_form = VIPInvitationForm(request.POST or None, prefix="vip")
    speaker_form = SpeakerForm(request.POST or None, request.FILES or None, prefix="speaker")
    sponsor_form = SponsorForm(request.POST or None, request.FILES or None, prefix="sponsor")
    for form in [vip_form, speaker_form, sponsor_form]:
        form.fields["event"].queryset = scoped_events(request)
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        form = {"vip": vip_form, "speaker": speaker_form, "sponsor": sponsor_form}.get(kind)
        if form and form.is_valid():
            form.save()
            messages.success(request, "تم حفظ البيانات.")
            return redirect("admin-people")
    context = {
        "vip_form": vip_form,
        "speaker_form": speaker_form,
        "sponsor_form": sponsor_form,
        "vip": scope_queryset(request.user, VIPInvitation.objects.select_related("event"))[:50],
        "speakers": scope_queryset(request.user, Speaker.objects.select_related("event"))[:50],
        "sponsors": scope_queryset(request.user, Sponsor.objects.select_related("event"))[:50],
        "volunteers": scope_queryset(request.user, Volunteer.objects.select_related("participant", "participant__event"))[:50],
    }
    return render(request, "core/admin_people.html", context)


@login_required
def feedback_admin(request):
    require_capability(request.user, "reports")
    surveys = scope_queryset(request.user, Survey.objects.select_related("event", "workshop").prefetch_related("questions"))[:100]
    responses = scope_queryset(request.user, SurveyResponse.objects.select_related("survey", "participant", "survey__event"))[:100]
    survey_form = SurveyForm(request.POST or None, prefix="survey")
    question_form = SurveyQuestionForm(request.POST or None, prefix="question")
    survey_form.fields["event"].queryset = scoped_events(request)
    survey_form.fields["workshop"].queryset = scope_queryset(request.user, Workshop.objects.all())
    question_form.fields["survey"].queryset = scope_queryset(request.user, Survey.objects.all())
    if request.method == "POST":
        if request.POST.get("form_kind") == "survey" and survey_form.is_valid():
            survey_form.save()
            messages.success(request, "تم حفظ الاستبيان.")
            return redirect("admin-feedback")
        if request.POST.get("form_kind") == "question" and question_form.is_valid():
            question_form.save()
            messages.success(request, "تم حفظ السؤال.")
            return redirect("admin-feedback")
    stats = responses.values("survey__title").annotate(total=Count("id"), avg=Sum("satisfaction_score") / Count("id"))
    return render(request, "core/admin_feedback.html", {"surveys": surveys, "responses": responses, "survey_form": survey_form, "question_form": question_form, "stats": stats})


@login_required
def media_admin(request):
    require_capability(request.user, "media")
    items = scope_queryset(request.user, MediaItem.objects.select_related("event"))[:120]
    form = MediaItemForm(request.POST or None, request.FILES or None)
    form.fields["event"].queryset = scoped_events(request)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        services.audit("media.saved", item, actor=request.user, request=request)
        messages.success(request, "تم حفظ عنصر المركز الإعلامي.")
        return redirect("admin-media")
    return render(request, "core/admin_media.html", {"items": items, "form": form})


@login_required
def finance_admin(request):
    require_capability(request.user, "finance")
    events = scoped_events(request)
    ticket_types = scope_queryset(request.user, TicketType.objects.select_related("event"))[:100]
    tickets = scope_queryset(request.user, Ticket.objects.select_related("event", "participant", "ticket_type"))[:150]
    expenses = scope_queryset(request.user, Expense.objects.select_related("event"))[:100]
    coupons = scope_queryset(request.user, Coupon.objects.select_related("event"))[:100]
    invoices = scope_queryset(request.user, Invoice.objects.select_related("event", "ticket", "participant"))[:120]
    refunds = scope_queryset(request.user, Refund.objects.select_related("event", "ticket", "participant", "processed_by"))[:100]
    ticket_type_form = TicketTypeForm(request.POST or None, prefix="ticket_type")
    coupon_form = CouponForm(request.POST or None, prefix="coupon")
    expense_form = ExpenseForm(request.POST or None, prefix="expense")
    invoice_form = InvoiceForm(request.POST or None, prefix="invoice")
    refund_form = RefundForm(request.POST or None, prefix="refund")
    issue_form = TicketIssueForm(request.POST or None, prefix="issue", events=events)
    ticket_type_form.fields["event"].queryset = events
    coupon_form.fields["event"].queryset = events
    expense_form.fields["event"].queryset = events
    invoice_form.fields["event"].queryset = events
    invoice_form.fields["ticket"].queryset = scope_queryset(request.user, Ticket.objects.select_related("event", "participant"))
    invoice_form.fields["participant"].queryset = scope_queryset(request.user, Participant.objects.filter(is_deleted=False))
    refund_form.fields["event"].queryset = events
    refund_form.fields["ticket"].queryset = scope_queryset(request.user, Ticket.objects.select_related("event", "participant"))
    refund_form.fields["participant"].queryset = scope_queryset(request.user, Participant.objects.filter(is_deleted=False))
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "ticket_type" and ticket_type_form.is_valid():
            ticket_type_form.save()
            messages.success(request, "تم حفظ نوع التذكرة.")
            return redirect("admin-finance")
        if kind == "coupon" and coupon_form.is_valid():
            coupon_form.save()
            messages.success(request, "تم حفظ كود الخصم.")
            return redirect("admin-finance")
        if kind == "expense" and expense_form.is_valid():
            expense_form.save()
            messages.success(request, "تم حفظ المصروف.")
            return redirect("admin-finance")
        if kind == "invoice" and invoice_form.is_valid():
            invoice = invoice_form.save()
            if invoice.ticket:
                invoice.ticket.invoice_number = invoice.invoice_number
                invoice.ticket.save(update_fields=["invoice_number", "updated_at"])
            messages.success(request, "تم حفظ الفاتورة.")
            return redirect("admin-finance")
        if kind == "refund" and refund_form.is_valid():
            refund = refund_form.save(commit=False)
            if refund.status in {Refund.Status.APPROVED, Refund.Status.PAID}:
                refund.processed_by = request.user
                refund.processed_at = timezone.now()
            refund.save()
            if refund.ticket and refund.status == Refund.Status.PAID:
                refund.ticket.payment_status = Ticket.PaymentStatus.REFUNDED
                refund.ticket.save(update_fields=["payment_status", "updated_at"])
            messages.success(request, "تم حفظ طلب الاسترداد.")
            return redirect("admin-finance")
        if kind in {"ticket_cancel", "ticket_reissue", "ticket_payment"}:
            ticket = get_object_or_404(
                scope_queryset(request.user, Ticket.objects.select_related("event", "participant", "ticket_type")),
                pk=request.POST.get("ticket"),
            )
            try:
                if kind == "ticket_cancel":
                    services.cancel_ticket(ticket, actor=request.user, request=request, note=request.POST.get("note", ""))
                    messages.success(request, "تم إلغاء التذكرة.")
                elif kind == "ticket_reissue":
                    services.reissue_ticket(ticket, actor=request.user, request=request)
                    messages.success(request, "تمت إعادة إصدار QR للتذكرة.")
                else:
                    services.update_ticket_payment(ticket, request.POST.get("payment_status"), actor=request.user, request=request)
                    messages.success(request, "تم تحديث حالة الدفع.")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
            return redirect("admin-finance")
        if kind == "issue" and issue_form.is_valid():
            try:
                ticket = issue_form.save()
                messages.success(request, f"تم إصدار التذكرة: {ticket.qr_code}")
                return redirect("admin-finance")
            except ValidationError as exc:
                messages.error(request, error_text(exc))
    revenue = scope_queryset(request.user, Ticket.objects.all()).aggregate(total=Sum("amount")).get("total") or 0
    expense_total = scope_queryset(request.user, Expense.objects.all()).aggregate(total=Sum("amount")).get("total") or 0
    refund_total = scope_queryset(request.user, Refund.objects.filter(status=Refund.Status.PAID)).aggregate(total=Sum("amount")).get("total") or 0
    return render(
        request,
        "core/admin_finance.html",
        {
            "ticket_types": ticket_types,
            "tickets": tickets,
            "expenses": expenses,
            "coupons": coupons,
            "invoices": invoices,
            "refunds": refunds,
            "ticket_type_form": ticket_type_form,
            "coupon_form": coupon_form,
            "expense_form": expense_form,
            "invoice_form": invoice_form,
            "refund_form": refund_form,
            "issue_form": issue_form,
            "revenue": revenue,
            "expense_total": expense_total,
            "refund_total": refund_total,
            "net": revenue - expense_total - refund_total,
            "payment_statuses": Ticket.PaymentStatus.choices,
        },
    )


@login_required
def platform_admin(request):
    require_super_admin(request.user)
    app_version_form = AppVersionForm(request.POST or None, prefix="app")
    plan_form = SubscriptionPlanForm(request.POST or None, prefix="plan")
    subscription_form = OrganizationSubscriptionForm(request.POST or None, prefix="subscription")
    backup_form = BackupJobForm(request.POST or None, prefix="backup")
    if request.method == "POST":
        kind = request.POST.get("form_kind")
        if kind == "app" and app_version_form.is_valid():
            app_version_form.save()
            messages.success(request, "تم حفظ إصدار التطبيق.")
            return redirect("admin-platform")
        if kind == "plan" and plan_form.is_valid():
            plan_form.save()
            messages.success(request, "تم حفظ خطة الاشتراك.")
            return redirect("admin-platform")
        if kind == "subscription" and subscription_form.is_valid():
            subscription_form.save()
            messages.success(request, "تم حفظ اشتراك الجهة.")
            return redirect("admin-platform")
        if kind == "backup" and backup_form.is_valid():
            organization = backup_form.cleaned_data.get("organization")
            job, data = services.create_backup_snapshot(organization=organization, actor=request.user)
            messages.success(request, f"تم إنشاء Snapshot: {job.id} - فعاليات {data['events']} ومشاركين {data['participants']}.")
            return redirect("admin-platform")
    context = {
        "app_version_form": app_version_form,
        "plan_form": plan_form,
        "subscription_form": subscription_form,
        "backup_form": backup_form,
        "app_versions": AppVersion.objects.all()[:20],
        "plans": SubscriptionPlan.objects.all()[:20],
        "subscriptions": OrganizationSubscription.objects.select_related("organization", "plan")[:50],
        "backups": BackupJob.objects.select_related("organization")[:50],
        "platform_stats": services.dashboard_stats(),
    }
    return render(request, "core/admin_platform.html", context)


@login_required
def event_final_report(request, event_id):
    require_capability(request.user, "reports")
    event = get_scoped_event_or_404(request, event_id)
    if request.GET.get("download") == "pdf":
        return HttpResponse(services.render_event_report_pdf(event, actor=request.user), content_type="application/pdf")
    snapshot = services.create_report_snapshot(event, actor=request.user)
    return render(request, "core/event_final_report.html", {"event": event, "snapshot": snapshot, "data": snapshot.data})


@login_required
def violations_admin(request):
    require_capability(request.user, "violations")
    type_form = ViolationTypeForm(request.POST or None, prefix="type")
    violation_form = IncidentViolationForm(request.POST or None, request.FILES or None, prefix="violation")
    type_form.fields["event"].queryset = scoped_events(request)
    violation_form.fields["event"].queryset = scoped_events(request)
    violation_form.fields["participant"].queryset = scope_queryset(request.user, Participant.objects.filter(is_deleted=False))
    if request.method == "POST":
        if request.POST.get("form_kind") == "type" and type_form.is_valid():
            type_form.save()
            messages.success(request, "تم حفظ نوع المخالفة.")
            return redirect("admin-violations")
        if request.POST.get("form_kind") == "violation" and violation_form.is_valid():
            violation = violation_form.save(commit=False)
            violation.reported_by = request.user
            violation.save()
            if violation.violation_type and violation.violation_type.blocks_certificate:
                participant = violation.participant
                participant.certificate_blocked = True
                participant.certificate_block_reason = f"مخالفة: {violation.violation_type.name}"
                participant.status = RegistrationStatus.CERTIFICATE_BLOCKED
                participant.save(update_fields=["certificate_blocked", "certificate_block_reason", "status", "updated_at"])
            messages.success(request, "تم تسجيل المخالفة.")
            return redirect("admin-violations")
    return render(request, "core/admin_violations.html", {"type_form": type_form, "violation_form": violation_form, "violations": scope_queryset(request.user, IncidentViolation.objects.select_related("event", "participant", "violation_type"))[:100]})


@login_required
def reports_admin(request, event_id=None):
    require_capability(request.user, "reports")
    event = get_scoped_event_or_404(request, event_id) if event_id else None
    profile = user_profile(request.user)
    organization = profile.organization if profile and profile.organization_id and not request.user.is_superuser else None
    stats = services.dashboard_stats(event=event, organization=organization)
    events = scoped_events(request)
    participants = scope_queryset(request.user, Participant.objects.filter(is_deleted=False))
    if event:
        participants = participants.filter(event=event)
    by_status = participants.values("status").order_by("status").annotate(total=Count("id"))
    return render(request, "core/admin_reports.html", {"event": event, "events": events, "stats": stats, "by_status": by_status})


@login_required
@require_POST
def event_state_action(request, event_id):
    require_capability(request.user, "manage_event")
    event = get_scoped_event_or_404(request, event_id)
    action = request.POST.get("action")
    if action == "toggle_maintenance":
        event.maintenance_mode = not event.maintenance_mode
        event.save(update_fields=["maintenance_mode", "updated_at"])
    elif action == "archive":
        event.archived = True
        event.save(update_fields=["archived", "updated_at"])
    elif action == "open_registration":
        event.registration_open = True
        event.save(update_fields=["registration_open", "updated_at"])
    elif action == "close_registration":
        event.registration_open = False
        event.save(update_fields=["registration_open", "updated_at"])
    services.audit("event.state_changed", event, actor=request.user, request=request, note=action)
    messages.success(request, "تم تحديث حالة الفعالية.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("admin-events"))
