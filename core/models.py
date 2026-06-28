import hashlib
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


def code(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def hall_qr_code():
    return code("HALL")


def registration_tracking_code():
    return code("REG")


def participant_qr_code():
    return code("QR")


def certificate_serial_number():
    return code("CERT")


def certificate_verification_code():
    return uuid.uuid4().hex


def support_tracking_code():
    return code("SUP")


def vip_qr_code():
    return code("VIP")


def ticket_qr_code():
    return code("TKT")


def invoice_code():
    return code("INV")


def upload_limit(value):
    if value.size > 8 * 1024 * 1024:
        raise ValidationError("حجم الملف يجب ألا يتجاوز 8 ميجابايت.")


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimestampedModel):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    ORGANIZATION_ADMIN = "organization_admin", "Organization Admin"
    EVENT_MANAGER = "event_manager", "Event Manager"
    REGISTRATION_MANAGER = "registration_manager", "Registration Manager"
    CHECKIN_STAFF = "checkin_staff", "Check-in Staff"
    WORKSHOP_MANAGER = "workshop_manager", "Workshop Manager"
    CERTIFICATE_MANAGER = "certificate_manager", "Certificate Manager"
    COMMUNICATION_MANAGER = "communication_manager", "Communication Manager"
    VOLUNTEER_MANAGER = "volunteer_manager", "Volunteer Manager"
    CRISIS_MANAGER = "crisis_manager", "Crisis Manager"
    FINANCE_MANAGER = "finance_manager", "Finance Manager"
    MEDIA_MANAGER = "media_manager", "Media Manager"
    VIP_MANAGER = "vip_manager", "VIP Manager"
    SPEAKER_MANAGER = "speaker_manager", "Speaker Manager"
    SPONSOR_MANAGER = "sponsor_manager", "Sponsor Manager"
    SUPPORT_AGENT = "support_agent", "Support Agent"
    AUDITOR = "auditor", "Auditor"
    VIEWER = "viewer", "Viewer"
    MOBILE_STUDENT = "mobile_student", "Mobile Student"
    MOBILE_SUPERVISOR = "mobile_supervisor", "Mobile Supervisor"
    MOBILE_VOLUNTEER = "mobile_volunteer", "Mobile Volunteer"


class ModuleCode(models.TextChoices):
    PUBLIC_REGISTRATION = "public_registration", "التسجيل الخارجي"
    INTERNAL_REGISTRATION = "internal_registration", "التسجيل الداخلي"
    MANUAL_REVIEW = "manual_review", "المراجعة اليدوية"
    AUTO_APPROVAL = "auto_approval", "القبول التلقائي"
    WAITLIST = "waitlist", "قائمة الانتظار"
    QR_TICKETS = "qr_tickets", "QR Tickets"
    CHECKIN = "checkin", "Check-in"
    CHECKOUT = "checkout", "Check-out"
    WORKSHOP_ATTENDANCE = "workshop_attendance", "حضور الورش"
    POINTS = "points", "نظام النقاط"
    BADGES = "badges", "نظام الأوسمة"
    CERTIFICATES = "certificates", "الشهادات"
    CERTIFICATE_EMAIL = "certificate_email", "إرسال الشهادات بالبريد"
    FIREBASE = "firebase", "Firebase Notifications"
    BROADCAST = "broadcast", "Broadcast"
    SUPPORT = "support", "طلبات الدعم"
    SOS = "sos", "SOS"
    VIOLATIONS = "violations", "المخالفات"
    VOLUNTEERS = "volunteers", "المتطوعون"
    VIP = "vip", "VIP"
    SPEAKERS = "speakers", "المتحدثون"
    SPONSORS = "sponsors", "الرعاة"
    FEEDBACK = "feedback", "التقييمات"
    PUBLIC_DISPLAYS = "public_displays", "شاشات العرض"
    MEDIA_CENTER = "media_center", "المركز الإعلامي"
    PAYMENTS = "payments", "المدفوعات"
    TICKETS = "tickets", "التذاكر"
    MAINTENANCE = "maintenance", "وضع الصيانة"
    ARCHIVE = "archive", "الأرشفة"
    APP_UPDATES = "app_updates", "تحديثات التطبيق"
    MOBILE_API = "mobile_api", "API للتطبيق"
    PUBLIC_VERIFY = "public_verify", "التحقق العام"
    ADVANCED_REPORTS = "advanced_reports", "التقارير المتقدمة"
    AI = "ai", "الذكاء الاصطناعي"


class RegistrationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    PENDING_REVIEW = "pending_review", "Pending Review"
    NEED_MORE_INFO = "need_more_info", "Need More Info"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    WAITLISTED = "waitlisted", "Waitlisted"
    CHECKED_IN = "checked_in", "Checked-in"
    CHECKED_OUT = "checked_out", "Checked-out"
    ATTENDED = "attended", "Attended"
    NO_SHOW = "no_show", "No Show"
    BANNED = "banned", "Banned"
    CERTIFICATE_BLOCKED = "certificate_blocked", "Certificate Blocked"


class Organization(SoftDeleteModel):
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True, allow_unicode=True)
    logo = models.ImageField(upload_to="organizations/logos/", blank=True)
    primary_color = models.CharField(max_length=20, default="#0f766e")
    accent_color = models.CharField(max_length=20, default="#f59e0b")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True) or code("org").lower()
        super().save(*args, **kwargs)


class Event(SoftDeleteModel):
    class EventType(models.TextChoices):
        CONFERENCE = "conference", "مؤتمر"
        TRAINING = "training", "تدريب"
        CAMP = "camp", "معسكر"
        SCHOOL = "school", "مدرسي"
        COMMUNITY = "community", "مبادرة"
        OTHER = "other", "أخرى"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="events")
    name = models.CharField(max_length=220)
    slug = models.SlugField(allow_unicode=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices, default=EventType.CONFERENCE)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    venue_name = models.CharField(max_length=220, blank=True)
    venue_address = models.CharField(max_length=300, blank=True)
    map_url = models.URLField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=0)
    registration_open = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    allow_registration_update = models.BooleanField(default=True)
    prevent_duplicate_checkin = models.BooleanField(default=True)
    require_feedback_for_certificate = models.BooleanField(default=False)
    min_attendance_percent_for_certificate = models.PositiveSmallIntegerField(default=60)
    logo = models.ImageField(upload_to="events/logos/", blank=True)
    banner = models.ImageField(upload_to="events/banners/", blank=True)
    primary_color = models.CharField(max_length=20, blank=True)
    accent_color = models.CharField(max_length=20, blank=True)
    public_instructions = models.TextField(blank=True)
    faq = models.JSONField(default=list, blank=True)
    terms = models.TextField(blank=True)
    privacy_policy = models.TextField(blank=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-starts_at"]
        unique_together = [("organization", "slug")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True) or code("evt").lower()
        super().save(*args, **kwargs)

    @property
    def effective_primary_color(self):
        return self.primary_color or self.organization.primary_color

    @property
    def effective_accent_color(self):
        return self.accent_color or self.organization.accent_color

    def module_enabled(self, module_code):
        if module_code == ModuleCode.MAINTENANCE and self.maintenance_mode:
            return True
        return self.modules.filter(code=module_code, enabled=True).exists()


class UserProfile(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=40, choices=Role.choices, default=Role.VIEWER)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    assigned_events = models.ManyToManyField(Event, blank=True, related_name="assigned_users")
    phone = models.CharField(max_length=40, blank=True)
    force_password_change = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.get_username()} - {self.get_role_display()}"

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN or self.user.is_superuser


class EventModule(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="modules")
    code = models.CharField(max_length=60, choices=ModuleCode.choices)
    label = models.CharField(max_length=120, blank=True)
    enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = [("event", "code")]

    def __str__(self):
        return f"{self.event} - {self.label or self.get_code_display()}"


class AuditLog(TimestampedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=80, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.entity_type} {self.entity_id}"


class EventDay(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="days")
    name = models.CharField(max_length=120)
    date = models.DateField()
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["date", "order"]
        unique_together = [("event", "date")]

    def __str__(self):
        return f"{self.event} - {self.name}"


class Track(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default="#2563eb")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Hall(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="halls")
    name = models.CharField(max_length=160)
    capacity = models.PositiveIntegerField(default=0)
    responsible_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    equipment = models.TextField(blank=True)
    qr_code = models.CharField(max_length=80, unique=True, default=hall_qr_code)
    area_type = models.CharField(max_length=60, default="general")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.event} - {self.name}"


class EducationAdministration(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="education_administrations")
    name = models.CharField(max_length=180)
    governorate = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["governorate", "name"]
        unique_together = [("organization", "name", "governorate")]

    def __str__(self):
        return self.name


class School(TimestampedModel):
    administration = models.ForeignKey(EducationAdministration, on_delete=models.PROTECT, related_name="schools")
    name = models.CharField(max_length=180)
    city = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("administration", "name")]

    def __str__(self):
        return self.name


class ParticipantGroup(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="groups")
    name = models.CharField(max_length=120)
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        unique_together = [("event", "name")]

    def __str__(self):
        return self.name


class RegistrationForm(TimestampedModel):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="registration_form")
    title = models.CharField(max_length=180, default="نموذج التسجيل")
    description = models.TextField(blank=True)
    is_open = models.BooleanField(default=True)
    duplicate_rules = models.JSONField(default=dict, blank=True)
    allow_file_uploads = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.event} - {self.title}"


class RegistrationField(TimestampedModel):
    class FieldType(models.TextChoices):
        TEXT = "text", "نص"
        NUMBER = "number", "رقم"
        EMAIL = "email", "بريد"
        PHONE = "phone", "هاتف"
        SINGLE_CHOICE = "single_choice", "اختيار واحد"
        MULTIPLE_CHOICE = "multiple_choice", "اختيار متعدد"
        DATE = "date", "تاريخ"
        FILE = "file", "ملف"
        CONSENT = "consent", "موافقة"
        TEXTAREA = "textarea", "نص طويل"

    form = models.ForeignKey(RegistrationForm, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(max_length=160)
    key = models.SlugField(max_length=120, allow_unicode=True)
    field_type = models.CharField(max_length=30, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)
    options = models.JSONField(default=list, blank=True)
    validation_rules = models.JSONField(default=dict, blank=True)
    visibility_rules = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("form", "key")]

    def __str__(self):
        return self.label


class Participant(SoftDeleteModel):
    class RegistrationType(models.TextChoices):
        STUDENT = "student", "طالب"
        VOLUNTEER = "volunteer", "متطوع"
        SUPERVISOR = "supervisor", "مشرف"
        GUEST = "guest", "ضيف"
        VIP = "vip", "VIP"
        SPEAKER = "speaker", "متحدث"
        MEDIA = "media", "إعلامي"
        SPONSOR = "sponsor", "راعي"
        COMPANY = "company", "شركة مشاركة"
        PARENT = "parent", "ولي أمر"

    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="participant_profiles")
    registration_type = models.CharField(max_length=30, choices=RegistrationType.choices, default=RegistrationType.STUDENT)
    full_name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40)
    email = models.EmailField(blank=True)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    education_administration = models.ForeignKey(EducationAdministration, on_delete=models.SET_NULL, null=True, blank=True)
    governorate = models.CharField(max_length=120, blank=True)
    national_id = models.CharField(max_length=40, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(3), MaxValueValidator(120)])
    gender = models.CharField(max_length=20, blank=True)
    guardian_name = models.CharField(max_length=160, blank=True)
    guardian_phone = models.CharField(max_length=40, blank=True)
    reason = models.TextField(blank=True)
    group = models.ForeignKey(ParticipantGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="participants")
    status = models.CharField(max_length=40, choices=RegistrationStatus.choices, default=RegistrationStatus.SUBMITTED)
    tracking_code = models.CharField(max_length=80, unique=True, default=registration_tracking_code)
    qr_code = models.CharField(max_length=120, unique=True, default=participant_qr_code)
    dynamic_answers = models.JSONField(default=dict, blank=True)
    duplicate_hash = models.CharField(max_length=64, db_index=True, blank=True)
    is_blacklisted = models.BooleanField(default=False)
    certificate_blocked = models.BooleanField(default=False)
    certificate_block_reason = models.TextField(blank=True)
    review_notes = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["event", "phone"]),
            models.Index(fields=["event", "email"]),
        ]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        base = f"{self.event_id}:{self.phone.lower()}:{self.email.lower()}:{self.national_id.lower()}"
        self.duplicate_hash = hashlib.sha256(base.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)


class UploadedDocument(TimestampedModel):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="documents")
    label = models.CharField(max_length=120)
    file = models.FileField(
        upload_to="participant_documents/",
        validators=[upload_limit, FileExtensionValidator(["jpg", "jpeg", "png", "pdf"])],
    )
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.participant} - {self.label}"


class Speaker(SoftDeleteModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="speakers")
    name = models.CharField(max_length=180)
    title = models.CharField(max_length=180, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to="speakers/", blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    technical_needs = models.TextField(blank=True)
    presentation_file = models.FileField(upload_to="speaker_files/", blank=True, validators=[upload_limit])
    public_profile = models.BooleanField(default=True)
    publishing_consent = models.BooleanField(default=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Session(TimestampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "لم تبدأ"
        LIVE = "live", "جارية"
        FINISHED = "finished", "انتهت"
        POSTPONED = "postponed", "تم التأجيل"
        ROOM_CHANGED = "room_changed", "تم تغيير القاعة"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    day = models.ForeignKey(EventDay, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    hall = models.ForeignKey(Hall, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    speakers = models.ManyToManyField(Speaker, blank=True, related_name="sessions")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NOT_STARTED)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title


class Workshop(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workshops")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    trainer = models.ForeignKey(Speaker, on_delete=models.SET_NULL, null=True, blank=True, related_name="workshops")
    hall = models.ForeignKey(Hall, on_delete=models.SET_NULL, null=True, blank=True, related_name="workshops")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=0)
    requirements = models.TextField(blank=True)
    registration_open = models.BooleanField(default=True)
    waitlist_enabled = models.BooleanField(default=True)
    points = models.IntegerField(default=0)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title

    @property
    def seats_taken(self):
        return self.registrations.filter(status__in=["registered", "attended"]).count()

    @property
    def seats_available(self):
        if not self.capacity:
            return 999999
        return max(self.capacity - self.seats_taken, 0)


class WorkshopRegistration(TimestampedModel):
    class Status(models.TextChoices):
        REGISTERED = "registered", "مسجل"
        WAITLISTED = "waitlisted", "انتظار"
        ATTENDED = "attended", "حضر"
        CANCELLED = "cancelled", "ملغي"

    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="registrations")
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="workshop_registrations")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REGISTERED)
    attended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("workshop", "participant")]
        ordering = ["-created_at"]

    def clean(self):
        if self.participant.event_id != self.workshop.event_id:
            raise ValidationError("المشارك والورشة يجب أن يكونا في نفس الفعالية.")
        if self.status in {self.Status.REGISTERED, self.Status.ATTENDED}:
            overlaps = WorkshopRegistration.objects.filter(
                participant=self.participant,
                status__in=[self.Status.REGISTERED, self.Status.ATTENDED],
                workshop__starts_at__lt=self.workshop.ends_at,
                workshop__ends_at__gt=self.workshop.starts_at,
            ).exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError("لا يمكن التسجيل في ورشتين متعارضتين في نفس الوقت.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CheckInLog(TimestampedModel):
    class Action(models.TextChoices):
        CHECKIN = "checkin", "Check-in"
        CHECKOUT = "checkout", "Check-out"
        WORKSHOP = "workshop", "Workshop Attendance"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="checkin_logs")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name="checkin_logs")
    workshop = models.ForeignKey(Workshop, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_logs")
    action = models.CharField(max_length=30, choices=Action.choices)
    code_scanned = models.CharField(max_length=140, blank=True)
    gate = models.CharField(max_length=120, blank=True)
    device = models.CharField(max_length=120, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    success = models.BooleanField(default=True)
    message = models.CharField(max_length=255, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [models.Index(fields=["event", "action", "checked_at"])]

    def __str__(self):
        return f"{self.action} - {self.participant or self.code_scanned}"


class StudentNote(TimestampedModel):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=80, default="general")
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True)
    workshop = models.ForeignKey(Workshop, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField()
    visible_to_student = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.participant} - {self.category}"


class PointTransaction(TimestampedModel):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="point_transactions")
    value = models.IntegerField()
    reason = models.CharField(max_length=180)
    source = models.CharField(max_length=80, default="manual")
    awarded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.participant} - {self.value}"


class PointRule(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="point_rules")
    name = models.CharField(max_length=160)
    trigger = models.CharField(max_length=80)
    value = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Badge(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="badges")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=80, default="award")
    points_required = models.IntegerField(default=0)
    attendance_percent_required = models.PositiveSmallIntegerField(default=0)
    auto_award = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ParticipantBadge(TimestampedModel):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    awarded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=180, blank=True)

    class Meta:
        unique_together = [("participant", "badge")]

    def __str__(self):
        return f"{self.participant} - {self.badge}"


class ViolationType(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="violation_types")
    name = models.CharField(max_length=160)
    default_action = models.CharField(max_length=120, default="warning")
    blocks_certificate = models.BooleanField(default=False)
    points_penalty = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class IncidentViolation(TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "مفتوحة"
        APPEALED = "appealed", "اعتراض"
        RESOLVED = "resolved", "تم الحل"
        CANCELLED = "cancelled", "ملغاة"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="violations")
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="violations")
    violation_type = models.ForeignKey(ViolationType, on_delete=models.SET_NULL, null=True, blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    action_taken = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    appeal_notes = models.TextField(blank=True)
    appeal_result = models.TextField(blank=True)
    attachment = models.FileField(upload_to="violations/", blank=True, validators=[upload_limit])

    class Meta:
        ordering = ["-created_at"]


class CertificateTemplate(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="certificate_templates")
    name = models.CharField(max_length=160)
    certificate_type = models.CharField(max_length=80, default="attendance")
    title = models.CharField(max_length=200, default="شهادة تقدير")
    body_template = models.TextField(default="تشهد إدارة الفعالية بأن {participant} قد شارك في {event}.")
    signature_name = models.CharField(max_length=160, blank=True)
    signature_title = models.CharField(max_length=160, blank=True)
    include_sponsor_logos = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Certificate(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        ISSUED = "issued", "صحيحة"
        CANCELLED = "cancelled", "ملغاة"
        BLOCKED = "blocked", "محظورة"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="certificates")
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="certificates")
    template = models.ForeignKey(CertificateTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    certificate_type = models.CharField(max_length=80, default="attendance")
    serial_number = models.CharField(max_length=80, unique=True, default=certificate_serial_number)
    verification_code = models.CharField(max_length=80, unique=True, default=certificate_verification_code)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ISSUED)
    issued_at = models.DateTimeField(default=timezone.now)
    sent_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.serial_number


class EmailTemplate(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="email_templates")
    key = models.CharField(max_length=80)
    subject = models.CharField(max_length=220)
    body = models.TextField()
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("event", "key")]

    def __str__(self):
        return f"{self.event} - {self.key}"


class EmailLog(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        MOCKED = "mocked", "Mocked"

    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="email_logs")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.CharField(max_length=40, default="mock")
    to_email = models.EmailField()
    subject = models.CharField(max_length=220)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.QUEUED)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.to_email} - {self.subject}"


class NotificationLog(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="notification_logs")
    recipient_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    audience = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=240)
    safe_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default="mocked")
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.status}"


class Broadcast(TimestampedModel):
    class Channel(models.TextChoices):
        EMAIL = "email", "بريد"
        PUSH = "push", "Push"
        IN_APP = "in_app", "داخل النظام"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="broadcasts")
    audience = models.CharField(max_length=120)
    channel = models.CharField(max_length=30, choices=Channel.choices)
    title = models.CharField(max_length=180)
    message = models.TextField()
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=40, default="draft")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SOSReport(TimestampedModel):
    class Status(models.TextChoices):
        NEW = "new", "جديد"
        IN_PROGRESS = "in_progress", "قيد المعالجة"
        ESCALATED = "escalated", "تم التصعيد"
        RESOLVED = "resolved", "تم الحل"
        CLOSED = "closed", "مغلق"
        FALSE_ALARM = "false_alarm", "بلاغ غير صحيح"

    class Category(models.TextChoices):
        MEDICAL = "medical", "طبي"
        SECURITY = "security", "أمني"
        CROWD = "crowd", "ازدحام"
        MISSING_STUDENT = "missing_student", "طالب مفقود"
        TECHNICAL = "technical", "تقني"
        ORGANIZATION = "organization", "تنظيم"
        INCIDENT = "incident", "مشادة"
        VIOLATION = "violation", "مخالفة"
        SUPPORT = "support", "دعم"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sos_reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=40, choices=Category.choices)
    priority = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(5)])
    location = models.CharField(max_length=180, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_sos_reports")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEW)
    description = models.TextField()
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "-priority", "-created_at"]


class SupportTicket(TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "مفتوح"
        WAITING = "waiting", "في انتظار"
        RESOLVED = "resolved", "تم الحل"
        CLOSED = "closed", "مغلق"
        REOPENED = "reopened", "معاد فتحه"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="support_tickets")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True)
    tracking_code = models.CharField(max_length=80, unique=True, default=support_tracking_code)
    category = models.CharField(max_length=80)
    priority = models.CharField(max_length=40, default="normal")
    subject = models.CharField(max_length=180)
    message = models.TextField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    attachment = models.FileField(upload_to="support/", blank=True, validators=[upload_limit])
    sla_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]


class SupportReply(TimestampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    public = models.BooleanField(default=True)
    attachment = models.FileField(upload_to="support_replies/", blank=True, validators=[upload_limit])

    class Meta:
        ordering = ["created_at"]


class Volunteer(TimestampedModel):
    class RoleChoice(models.TextChoices):
        RECEPTION = "reception", "استقبال"
        CHECKIN = "checkin", "تسجيل حضور"
        HALL = "hall", "تنظيم قاعة"
        TECH = "tech", "دعم فني"
        MEDIA = "media", "ميديا"
        VIP = "vip", "VIP"
        SECURITY = "security", "أمن داخلي"
        WORKSHOPS = "workshops", "ورش"
        BACKSTAGE = "backstage", "Backstage"
        EMERGENCY = "emergency", "طوارئ"
        LOGISTICS = "logistics", "Logistics"

    participant = models.OneToOneField(Participant, on_delete=models.CASCADE, related_name="volunteer_profile")
    role = models.CharField(max_length=40, choices=RoleChoice.choices, default=RoleChoice.RECEPTION)
    area = models.CharField(max_length=120, blank=True)
    accepted = models.BooleanField(default=False)
    performance_score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.participant.full_name} - {self.get_role_display()}"


class VolunteerShift(TimestampedModel):
    class ShiftType(models.TextChoices):
        MORNING = "morning", "صباحي"
        EVENING = "evening", "مسائي"
        FULL_DAY = "full_day", "يوم كامل"
        CUSTOM = "custom", "مخصص"

    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name="shifts")
    shift_type = models.CharField(max_length=30, choices=ShiftType.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=40, default="scheduled")

    def __str__(self):
        return f"{self.volunteer} - {self.get_shift_type_display()}"


class VIPInvitation(TimestampedModel):
    class Status(models.TextChoices):
        SENT = "sent", "أرسلت"
        VIEWED = "viewed", "شوهدت"
        CONFIRMED = "confirmed", "تم التأكيد"
        ATTENDED = "attended", "حضر"
        APOLOGIZED = "apologized", "اعتذر"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="vip_invitations")
    name = models.CharField(max_length=180)
    title = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    qr_code = models.CharField(max_length=120, unique=True, default=vip_qr_code)
    reserved_seat = models.CharField(max_length=80, blank=True)
    special_entrance = models.CharField(max_length=120, blank=True)
    companions = models.PositiveSmallIntegerField(default=0)
    protocol_notes = models.TextField(blank=True)
    expected_arrival = models.DateTimeField(null=True, blank=True)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    car_number = models.CharField(max_length=60, blank=True)
    seating_area = models.CharField(max_length=120, blank=True)
    has_speech = models.BooleanField(default=False)
    needs_certificate_or_trophy = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SENT)

    class Meta:
        ordering = ["name"]


class Sponsor(TimestampedModel):
    class Level(models.TextChoices):
        MAIN = "main", "Main"
        GOLD = "gold", "Gold"
        SILVER = "silver", "Silver"
        BRONZE = "bronze", "Bronze"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sponsors")
    name = models.CharField(max_length=180)
    logo = models.ImageField(upload_to="sponsors/", blank=True)
    website = models.URLField(blank=True)
    level = models.CharField(max_length=30, choices=Level.choices, default=Level.BRONZE)
    sponsorship_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    benefits = models.TextField(blank=True)
    show_on_site = models.BooleanField(default=True)
    show_on_certificate = models.BooleanField(default=False)
    show_on_display = models.BooleanField(default=True)
    booth = models.CharField(max_length=120, blank=True)
    representative_name = models.CharField(max_length=180, blank=True)
    visits_count = models.PositiveIntegerField(default=0)
    scans_count = models.PositiveIntegerField(default=0)
    audience_interactions = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["level", "name"]

    def __str__(self):
        return self.name


class MediaItem(TimestampedModel):
    class Type(models.TextChoices):
        NEWS = "news", "خبر"
        PRESS = "press", "بيان صحفي"
        IMAGE = "image", "صورة"
        VIDEO = "video", "فيديو"
        PRESS_KIT = "press_kit", "Press Kit"
        SOCIAL = "social", "منشور"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="media_items")
    type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    file = models.FileField(upload_to="media_center/", blank=True, validators=[upload_limit])
    external_url = models.URLField(blank=True)
    published = models.BooleanField(default=False)


class Survey(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="surveys")
    workshop = models.ForeignKey(Workshop, on_delete=models.SET_NULL, null=True, blank=True, related_name="surveys")
    title = models.CharField(max_length=180)
    active = models.BooleanField(default=True)
    certificate_required = models.BooleanField(default=False)


class SurveyQuestion(TimestampedModel):
    class QuestionType(models.TextChoices):
        STARS = "stars", "نجوم"
        CHOICE = "choice", "اختيار"
        TEXT = "text", "نص"
        EMOJI = "emoji", "Emoji"
        NPS = "nps", "NPS"
        BEFORE_AFTER = "before_after", "قبل وبعد"

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    text = models.CharField(max_length=240)
    question_type = models.CharField(max_length=30, choices=QuestionType.choices)
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]


class SurveyResponse(TimestampedModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True)
    answers = models.JSONField(default=dict)
    satisfaction_score = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("survey", "participant")]


class TicketType(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="EGP")
    capacity = models.PositiveIntegerField(default=0)
    early_bird_until = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)


class Coupon(TimestampedModel):
    class DiscountType(models.TextChoices):
        PERCENT = "percent", "نسبة"
        FIXED = "fixed", "قيمة ثابتة"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="coupons")
    code = models.CharField(max_length=60)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(default=0)
    used_count = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("event", "code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.event} - {self.code}"


class Ticket(TimestampedModel):
    class PaymentStatus(models.TextChoices):
        FREE = "free", "Free"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"
        FAILED = "failed", "Failed"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="tickets")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.SET_NULL, null=True, blank=True)
    qr_code = models.CharField(max_length=120, unique=True, default=ticket_qr_code)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    cancelled = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=30, choices=PaymentStatus.choices, default=PaymentStatus.FREE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=60, blank=True)
    invoice_number = models.CharField(max_length=80, blank=True)
    receipt_number = models.CharField(max_length=80, blank=True)


class Invoice(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        ISSUED = "issued", "صادرة"
        PAID = "paid", "مدفوعة"
        CANCELLED = "cancelled", "ملغاة"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="invoices")
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    invoice_number = models.CharField(max_length=80, unique=True, default=invoice_code)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ISSUED)
    due_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number


class Refund(TimestampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "مطلوب"
        APPROVED = "approved", "مقبول"
        PAID = "paid", "تم الدفع"
        REJECTED = "rejected", "مرفوض"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="refunds")
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name="refunds")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=240)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REQUESTED)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.participant or self.ticket} - {self.amount}"


class Expense(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="expenses")
    category = models.CharField(max_length=120)
    description = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateField(null=True, blank=True)


class ReportSnapshot(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="report_snapshots")
    report_type = models.CharField(max_length=80)
    title = models.CharField(max_length=180)
    data = models.JSONField(default=dict)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)


class AppVersion(TimestampedModel):
    platform = models.CharField(max_length=40, default="android")
    version = models.CharField(max_length=40)
    apk_url = models.URLField(blank=True)
    force_update = models.BooleanField(default=False)
    update_message = models.CharField(max_length=240, blank=True)
    min_supported_version = models.CharField(max_length=40, blank=True)
    release_notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    released_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-released_at"]


class AIInsight(TimestampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ai_insights")
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True)
    insight_type = models.CharField(max_length=80)
    score = models.FloatField(default=0)
    summary = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    reviewed = models.BooleanField(default=False)


class BackupJob(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    job_type = models.CharField(max_length=40, default="backup")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.QUEUED)
    file = models.FileField(upload_to="backups/", blank=True)
    error = models.TextField(blank=True)


class SubscriptionPlan(TimestampedModel):
    name = models.CharField(max_length=120)
    max_events = models.PositiveIntegerField(default=1)
    max_participants = models.PositiveIntegerField(default=500)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    features = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class OrganizationSubscription(TimestampedModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    starts_at = models.DateField()
    ends_at = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    email_quota_used = models.PositiveIntegerField(default=0)
    push_quota_used = models.PositiveIntegerField(default=0)
    certificate_quota_used = models.PositiveIntegerField(default=0)


def profile_for(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


from django.db.models.signals import post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_save, sender=get_user_model())
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
