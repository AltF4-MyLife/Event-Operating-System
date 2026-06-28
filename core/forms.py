from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from . import services
from .models import (
    AppVersion,
    BackupJob,
    Badge,
    Broadcast,
    CertificateTemplate,
    CheckInLog,
    Coupon,
    EducationAdministration,
    EmailTemplate,
    Event,
    EventDay,
    EventModule,
    Expense,
    Hall,
    IncidentViolation,
    Invoice,
    MediaItem,
    Organization,
    OrganizationSubscription,
    Participant,
    ParticipantBadge,
    ParticipantGroup,
    PointRule,
    RegistrationField,
    RegistrationForm,
    RegistrationStatus,
    Refund,
    Role,
    SOSReport,
    School,
    Session,
    Sponsor,
    Speaker,
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
)


User = get_user_model()


class RTLModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{classes} input".strip()
            field.widget.attrs.setdefault("dir", "rtl")


class OrganizationForm(RTLModelForm):
    class Meta:
        model = Organization
        fields = ["name", "slug", "logo", "primary_color", "accent_color", "contact_email", "contact_phone", "address", "website", "is_active"]


class EventForm(RTLModelForm):
    class Meta:
        model = Event
        fields = [
            "organization",
            "name",
            "slug",
            "event_type",
            "short_description",
            "description",
            "venue_name",
            "venue_address",
            "map_url",
            "starts_at",
            "ends_at",
            "capacity",
            "registration_open",
            "maintenance_mode",
            "archived",
            "prevent_duplicate_checkin",
            "require_feedback_for_certificate",
            "min_attendance_percent_for_certificate",
            "primary_color",
            "accent_color",
            "public_instructions",
            "terms",
            "privacy_policy",
        ]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "public_instructions": forms.Textarea(attrs={"rows": 3}),
            "terms": forms.Textarea(attrs={"rows": 3}),
            "privacy_policy": forms.Textarea(attrs={"rows": 3}),
        }


class AdminUserCreateForm(forms.Form):
    username = forms.CharField(label="اسم المستخدم", max_length=150)
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    first_name = forms.CharField(label="الاسم الأول", required=False, max_length=150)
    last_name = forms.CharField(label="اسم العائلة", required=False, max_length=150)
    password = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput)
    role = forms.ChoiceField(label="الدور", choices=Role.choices)
    organization = forms.ModelChoiceField(label="الجهة", queryset=Organization.objects.none(), required=False)
    assigned_events = forms.ModelMultipleChoiceField(label="فعاليات مسموحة", queryset=Event.objects.none(), required=False)
    is_staff = forms.BooleanField(label="دخول لوحة الإدارة", required=False, initial=True)
    is_active = forms.BooleanField(label="مفعل", required=False, initial=True)

    def __init__(self, *args, organizations=None, events=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizations is not None:
            self.fields["organization"].queryset = organizations
        if events is not None:
            self.fields["assigned_events"].queryset = events
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("اسم المستخدم موجود بالفعل.")
        return username

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
            is_staff=self.cleaned_data.get("is_staff", True),
            is_active=self.cleaned_data.get("is_active", True),
        )
        profile = user.profile
        profile.role = self.cleaned_data["role"]
        profile.organization = self.cleaned_data.get("organization")
        profile.save()
        profile.assigned_events.set(self.cleaned_data.get("assigned_events", []))
        return user


class UserRoleUpdateForm(forms.Form):
    role = forms.ChoiceField(label="الدور", choices=Role.choices)
    organization = forms.ModelChoiceField(label="الجهة", queryset=Organization.objects.none(), required=False)
    assigned_events = forms.ModelMultipleChoiceField(label="فعاليات مسموحة", queryset=Event.objects.none(), required=False)
    is_active = forms.BooleanField(label="مفعل", required=False)
    is_staff = forms.BooleanField(label="دخول لوحة الإدارة", required=False)

    def __init__(self, *args, user=None, organizations=None, events=None, **kwargs):
        self.user = user
        initial = kwargs.pop("initial", {})
        if user is not None:
            profile = user.profile
            initial = {
                **initial,
                "role": profile.role,
                "organization": profile.organization_id,
                "assigned_events": profile.assigned_events.values_list("id", flat=True),
                "is_active": user.is_active,
                "is_staff": user.is_staff,
            }
        super().__init__(*args, initial=initial, **kwargs)
        if organizations is not None:
            self.fields["organization"].queryset = organizations
        if events is not None:
            self.fields["assigned_events"].queryset = events
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"

    def save(self):
        profile = self.user.profile
        profile.role = self.cleaned_data["role"]
        profile.organization = self.cleaned_data.get("organization")
        profile.save()
        profile.assigned_events.set(self.cleaned_data.get("assigned_events", []))
        self.user.is_active = self.cleaned_data.get("is_active", False)
        self.user.is_staff = self.cleaned_data.get("is_staff", False)
        self.user.save(update_fields=["is_active", "is_staff"])
        return self.user


class EventModuleForm(RTLModelForm):
    class Meta:
        model = EventModule
        fields = ["enabled", "config"]


class RegistrationFormSettingsForm(RTLModelForm):
    class Meta:
        model = RegistrationForm
        fields = ["title", "description", "is_open", "duplicate_rules", "allow_file_uploads"]


class RegistrationFieldForm(RTLModelForm):
    class Meta:
        model = RegistrationField
        fields = ["label", "key", "field_type", "required", "order", "options", "validation_rules", "visibility_rules", "is_active"]


class EducationAdministrationForm(RTLModelForm):
    class Meta:
        model = EducationAdministration
        fields = ["organization", "name", "governorate"]


class SchoolForm(RTLModelForm):
    class Meta:
        model = School
        fields = ["administration", "name", "city", "is_active"]


class ParticipantGroupForm(RTLModelForm):
    class Meta:
        model = ParticipantGroup
        fields = ["event", "name", "supervisor", "capacity"]


class ParticipantUpdateForm(RTLModelForm):
    class Meta:
        model = Participant
        fields = [
            "registration_type",
            "full_name",
            "phone",
            "email",
            "school",
            "education_administration",
            "governorate",
            "national_id",
            "age",
            "gender",
            "guardian_name",
            "guardian_phone",
            "reason",
            "group",
            "status",
            "is_blacklisted",
            "certificate_blocked",
            "certificate_block_reason",
            "review_notes",
        ]
        labels = {
            "registration_type": "نوع التسجيل",
            "full_name": "الاسم الكامل",
            "phone": "الهاتف",
            "email": "البريد",
            "school": "المدرسة",
            "education_administration": "الإدارة التعليمية",
            "governorate": "المحافظة",
            "national_id": "الرقم القومي",
            "age": "السن",
            "gender": "النوع",
            "guardian_name": "ولي الأمر",
            "guardian_phone": "هاتف ولي الأمر",
            "reason": "سبب الحضور",
            "group": "المجموعة",
            "status": "الحالة",
            "is_blacklisted": "محظور",
            "certificate_blocked": "منع شهادة",
            "certificate_block_reason": "سبب منع الشهادة",
            "review_notes": "ملاحظات المراجعة",
        }
        widgets = {"reason": forms.Textarea(attrs={"rows": 3}), "certificate_block_reason": forms.Textarea(attrs={"rows": 3}), "review_notes": forms.Textarea(attrs={"rows": 3})}


class UploadedDocumentForm(RTLModelForm):
    class Meta:
        model = UploadedDocument
        fields = ["label", "file", "verified"]
        labels = {"label": "اسم المستند", "file": "الملف", "verified": "تم التحقق"}


class EventDayForm(RTLModelForm):
    class Meta:
        model = EventDay
        fields = ["event", "name", "date", "order"]
        labels = {"event": "الفعالية", "name": "اسم اليوم", "date": "التاريخ", "order": "الترتيب"}
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class TrackForm(RTLModelForm):
    class Meta:
        model = Track
        fields = ["event", "name", "description", "color"]
        labels = {"event": "الفعالية", "name": "اسم المسار", "description": "الوصف", "color": "اللون"}
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "color": forms.TextInput(attrs={"type": "color"})}


class HallForm(RTLModelForm):
    class Meta:
        model = Hall
        fields = ["event", "name", "capacity", "responsible_user", "equipment", "area_type", "is_active"]
        labels = {
            "event": "الفعالية",
            "name": "اسم القاعة",
            "capacity": "السعة",
            "responsible_user": "المسؤول",
            "equipment": "التجهيزات",
            "area_type": "نوع المنطقة",
            "is_active": "مفعلة",
        }
        widgets = {"equipment": forms.Textarea(attrs={"rows": 3})}


class PublicRegistrationForm(forms.Form):
    registration_type = forms.ChoiceField(label="نوع التسجيل", choices=Participant.RegistrationType.choices)
    full_name = forms.CharField(label="الاسم الكامل", max_length=180)
    phone = forms.CharField(label="رقم الهاتف", max_length=40)
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    governorate = forms.CharField(label="المحافظة", required=False, max_length=120)
    national_id = forms.CharField(label="الرقم القومي", required=False, max_length=40)
    age = forms.IntegerField(label="السن", required=False, min_value=3, max_value=120)
    gender = forms.CharField(label="النوع", required=False, max_length=20)
    guardian_name = forms.CharField(label="اسم ولي الأمر", required=False, max_length=160)
    guardian_phone = forms.CharField(label="هاتف ولي الأمر", required=False, max_length=40)
    reason = forms.CharField(label="سبب الحضور", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, event, **kwargs):
        self.event = event
        self.registration_form = services.ensure_registration_form(event)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"
        for extra in self.registration_form.fields.filter(is_active=True):
            name = f"field_{extra.key}"
            if extra.key in self.fields:
                continue
            kwargs = {"label": extra.label, "required": extra.required}
            if extra.field_type == RegistrationField.FieldType.TEXTAREA:
                field = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **kwargs)
            elif extra.field_type == RegistrationField.FieldType.EMAIL:
                field = forms.EmailField(**kwargs)
            elif extra.field_type == RegistrationField.FieldType.NUMBER:
                field = forms.IntegerField(**kwargs)
            elif extra.field_type == RegistrationField.FieldType.DATE:
                field = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **kwargs)
            elif extra.field_type == RegistrationField.FieldType.FILE:
                field = forms.FileField(**kwargs)
            elif extra.field_type == RegistrationField.FieldType.CONSENT:
                field = forms.BooleanField(**kwargs)
            elif extra.field_type == RegistrationField.FieldType.SINGLE_CHOICE:
                options = [(value, value) for value in extra.options]
                field = forms.ChoiceField(choices=options, **kwargs)
            elif extra.field_type == RegistrationField.FieldType.MULTIPLE_CHOICE:
                options = [(value, value) for value in extra.options]
                field = forms.MultipleChoiceField(choices=options, widget=forms.CheckboxSelectMultiple, **kwargs)
            else:
                field = forms.CharField(**kwargs)
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"
            self.fields[name] = field

    def save(self, request=None):
        if not self.is_valid():
            raise ValidationError(self.errors)
        data = {key: value for key, value in self.cleaned_data.items() if not key.startswith("field_")}
        data["dynamic_answers"] = {
            key.removeprefix("field_"): value
            for key, value in self.cleaned_data.items()
            if key.startswith("field_") and not hasattr(value, "read")
        }
        return services.register_participant(self.event, data, request=request)


class CheckInForm(forms.Form):
    action = forms.ChoiceField(label="الإجراء", choices=[(CheckInLog.Action.CHECKIN, "تسجيل حضور"), (CheckInLog.Action.CHECKOUT, "تسجيل خروج")], initial=CheckInLog.Action.CHECKIN)
    code = forms.CharField(label="QR أو كود المتابعة", max_length=140)
    gate = forms.CharField(label="البوابة", required=False, max_length=120)
    device = forms.CharField(label="الجهاز", required=False, max_length=120)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"


class ParticipantImportForm(forms.Form):
    file = forms.FileField(label="ملف Excel")
    default_status = forms.ChoiceField(label="حالة التسجيل الافتراضية", choices=Participant._meta.get_field("status").choices, initial="submitted")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"


class BulkReviewForm(forms.Form):
    action = forms.ChoiceField(
        label="الإجراء الجماعي",
        choices=[
            ("approve", "قبول"),
            ("reject", "رفض"),
            ("waitlist", "قائمة انتظار"),
            ("need_info", "طلب استكمال"),
            ("ban", "حظر"),
            ("block_certificate", "منع شهادة"),
        ],
    )
    note = forms.CharField(label="ملاحظة", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"


class WorkshopAttendanceForm(forms.Form):
    workshop = forms.ModelChoiceField(label="الورشة", queryset=Workshop.objects.none())
    code = forms.CharField(label="QR أو كود المتابعة", max_length=140)
    gate = forms.CharField(label="القاعة/البوابة", required=False, max_length=120)
    device = forms.CharField(label="الجهاز", required=False, max_length=120)

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event:
            self.fields["workshop"].queryset = event.workshops.all()
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"


class WorkshopForm(RTLModelForm):
    class Meta:
        model = Workshop
        fields = ["event", "title", "description", "trainer", "hall", "starts_at", "ends_at", "capacity", "requirements", "registration_open", "waitlist_enabled", "points"]
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}), "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class SessionForm(RTLModelForm):
    class Meta:
        model = Session
        fields = ["event", "day", "track", "hall", "speakers", "title", "description", "starts_at", "ends_at", "status", "is_public"]
        labels = {
            "event": "الفعالية",
            "day": "اليوم",
            "track": "المسار",
            "hall": "القاعة",
            "speakers": "المتحدثون",
            "title": "العنوان",
            "description": "الوصف",
            "starts_at": "يبدأ في",
            "ends_at": "ينتهي في",
            "status": "الحالة",
            "is_public": "ظاهر للجمهور",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        starts_at = cleaned.get("starts_at")
        ends_at = cleaned.get("ends_at")
        if starts_at and ends_at and starts_at >= ends_at:
            self.add_error("ends_at", "وقت النهاية يجب أن يكون بعد وقت البداية.")
        if not event:
            return cleaned
        for field_name in ["day", "track", "hall"]:
            item = cleaned.get(field_name)
            if item and item.event_id != event.id:
                self.add_error(field_name, "هذا الاختيار لا يتبع نفس الفعالية.")
        for speaker in cleaned.get("speakers", []):
            if speaker.event_id != event.id:
                self.add_error("speakers", "كل المتحدثين يجب أن يتبعوا نفس الفعالية.")
                break
        return cleaned


class VolunteerForm(RTLModelForm):
    class Meta:
        model = Volunteer
        fields = ["participant", "role", "area", "accepted", "performance_score", "notes"]
        labels = {
            "participant": "المشارك",
            "role": "الدور",
            "area": "المنطقة",
            "accepted": "مقبول",
            "performance_score": "تقييم الأداء",
            "notes": "ملاحظات",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class VolunteerShiftForm(RTLModelForm):
    class Meta:
        model = VolunteerShift
        fields = ["volunteer", "shift_type", "starts_at", "ends_at", "location", "status"]
        labels = {
            "volunteer": "المتطوع",
            "shift_type": "نوع الشيفت",
            "starts_at": "يبدأ في",
            "ends_at": "ينتهي في",
            "location": "الموقع",
            "status": "الحالة",
        }
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}), "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get("starts_at")
        ends_at = cleaned.get("ends_at")
        if starts_at and ends_at and starts_at >= ends_at:
            self.add_error("ends_at", "وقت النهاية يجب أن يكون بعد وقت البداية.")
        return cleaned


class StudentNoteForm(RTLModelForm):
    class Meta:
        model = StudentNote
        fields = ["participant", "category", "session", "workshop", "note", "visible_to_student"]
        labels = {
            "participant": "الطالب",
            "category": "التصنيف",
            "session": "الجلسة",
            "workshop": "الورشة",
            "note": "الملاحظة",
            "visible_to_student": "ظاهرة للطالب",
        }
        widgets = {"note": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned = super().clean()
        participant = cleaned.get("participant")
        if not participant:
            return cleaned
        for field_name in ["session", "workshop"]:
            item = cleaned.get(field_name)
            if item and item.event_id != participant.event_id:
                self.add_error(field_name, "هذا الاختيار لا يتبع فعالية الطالب.")
        return cleaned


class PointRuleForm(RTLModelForm):
    trigger = forms.ChoiceField(
        label="المحفز",
        choices=[
            ("checkin", "تسجيل حضور"),
            ("checkout", "تسجيل خروج"),
            ("workshop_attendance", "حضور ورشة"),
            ("feedback", "إكمال تقييم"),
            ("manual", "منح يدوي"),
            ("volunteer_shift", "حضور شيفت متطوع"),
        ],
    )

    class Meta:
        model = PointRule
        fields = ["event", "name", "trigger", "value", "enabled"]
        labels = {"event": "الفعالية", "name": "اسم القاعدة", "value": "النقاط", "enabled": "مفعلة"}


class BadgeForm(RTLModelForm):
    class Meta:
        model = Badge
        fields = ["event", "name", "description", "icon", "points_required", "attendance_percent_required", "auto_award"]
        labels = {
            "event": "الفعالية",
            "name": "اسم الوسام",
            "description": "الوصف",
            "icon": "الأيقونة",
            "points_required": "النقاط المطلوبة",
            "attendance_percent_required": "نسبة الحضور المطلوبة",
            "auto_award": "منح تلقائي",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AwardPointsForm(forms.Form):
    event = forms.ModelChoiceField(label="الفعالية", queryset=Event.objects.none())
    participant = forms.ModelChoiceField(label="المشارك", queryset=Participant.objects.none())
    value = forms.IntegerField(label="النقاط")
    reason = forms.CharField(label="السبب", max_length=180)

    def __init__(self, *args, events=None, participants=None, **kwargs):
        super().__init__(*args, **kwargs)
        if events is not None:
            self.fields["event"].queryset = events
        if participants is not None:
            self.fields["participant"].queryset = participants
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        participant = cleaned.get("participant")
        if event and participant and participant.event_id != event.id:
            self.add_error("participant", "المشارك لا يتبع هذه الفعالية.")
        return cleaned

    def save(self, actor=None):
        return services.award_points(
            self.cleaned_data["participant"],
            self.cleaned_data["value"],
            self.cleaned_data["reason"],
            actor=actor,
            source="manual",
        )


class AwardBadgeForm(forms.Form):
    event = forms.ModelChoiceField(label="الفعالية", queryset=Event.objects.none())
    participant = forms.ModelChoiceField(label="المشارك", queryset=Participant.objects.none())
    badge = forms.ModelChoiceField(label="الوسام", queryset=Badge.objects.none())
    reason = forms.CharField(label="السبب", max_length=180, required=False)

    def __init__(self, *args, events=None, participants=None, badges=None, **kwargs):
        super().__init__(*args, **kwargs)
        if events is not None:
            self.fields["event"].queryset = events
        if participants is not None:
            self.fields["participant"].queryset = participants
        if badges is not None:
            self.fields["badge"].queryset = badges
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        participant = cleaned.get("participant")
        badge = cleaned.get("badge")
        if event and participant and participant.event_id != event.id:
            self.add_error("participant", "المشارك لا يتبع هذه الفعالية.")
        if event and badge and badge.event_id != event.id:
            self.add_error("badge", "الوسام لا يتبع هذه الفعالية.")
        return cleaned

    def save(self, actor=None):
        award, _ = ParticipantBadge.objects.get_or_create(
            participant=self.cleaned_data["participant"],
            badge=self.cleaned_data["badge"],
            defaults={"awarded_by": actor, "reason": self.cleaned_data.get("reason", "")},
        )
        return award


class SupportTicketForm(RTLModelForm):
    class Meta:
        model = SupportTicket
        fields = ["category", "priority", "subject", "message", "attachment"]


class SupportReplyForm(RTLModelForm):
    class Meta:
        model = SupportReply
        fields = ["message", "public", "attachment"]


class BroadcastForm(RTLModelForm):
    class Meta:
        model = Broadcast
        fields = ["event", "audience", "channel", "title", "message", "scheduled_at"]
        labels = {"event": "الفعالية", "audience": "الجمهور", "channel": "القناة", "title": "العنوان", "message": "الرسالة", "scheduled_at": "موعد الإرسال"}
        widgets = {"scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}), "message": forms.Textarea(attrs={"rows": 4})}


class EmailTemplateForm(RTLModelForm):
    class Meta:
        model = EmailTemplate
        fields = ["event", "key", "subject", "body", "active"]
        labels = {"event": "الفعالية", "key": "المفتاح", "subject": "العنوان", "body": "القالب", "active": "مفعل"}
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}


class DirectParticipantEmailForm(forms.Form):
    event = forms.ModelChoiceField(label="الفعالية", queryset=Event.objects.none())
    participant = forms.ModelChoiceField(label="المشارك", queryset=Participant.objects.none())
    template = forms.ModelChoiceField(label="قالب البريد", queryset=EmailTemplate.objects.none(), required=False)
    subject = forms.CharField(label="العنوان", max_length=220, required=False)
    body = forms.CharField(label="الرسالة", required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, events=None, participants=None, templates=None, **kwargs):
        super().__init__(*args, **kwargs)
        if events is not None:
            self.fields["event"].queryset = events
        if participants is not None:
            self.fields["participant"].queryset = participants
        if templates is not None:
            self.fields["template"].queryset = templates.filter(active=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        participant = cleaned.get("participant")
        template = cleaned.get("template")
        if event and participant and participant.event_id != event.id:
            self.add_error("participant", "المشارك لا يتبع هذه الفعالية.")
        if event and template and template.event_id != event.id:
            self.add_error("template", "القالب لا يتبع هذه الفعالية.")
        if not template and (not cleaned.get("subject") or not cleaned.get("body")):
            raise ValidationError("اختر قالبًا أو اكتب العنوان والرسالة.")
        if participant and not participant.email:
            self.add_error("participant", "لا يوجد بريد إلكتروني لهذا المشارك.")
        return cleaned

    def save(self, actor=None):
        template = self.cleaned_data.get("template")
        participant = self.cleaned_data["participant"]
        if template:
            return services.send_templated_email(template, participant, actor=actor)
        event = self.cleaned_data["event"]
        subject = services.render_message_template(self.cleaned_data["subject"], event, participant)
        body = services.render_message_template(self.cleaned_data["body"], event, participant)
        return services.send_event_email(event, participant.email, subject, body, participant=participant)


class PushNotificationForm(forms.Form):
    event = forms.ModelChoiceField(label="الفعالية", queryset=Event.objects.none())
    audience = forms.CharField(label="الجمهور", max_length=120, required=False)
    title = forms.CharField(label="العنوان", max_length=160)
    body = forms.CharField(label="النص", max_length=240, widget=forms.Textarea(attrs={"rows": 3}))
    payload = forms.JSONField(label="Payload آمن", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, events=None, **kwargs):
        super().__init__(*args, **kwargs)
        if events is not None:
            self.fields["event"].queryset = events
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"

    def save(self):
        return services.send_push(
            self.cleaned_data["event"],
            self.cleaned_data["title"],
            self.cleaned_data["body"],
            audience=self.cleaned_data.get("audience", ""),
            payload=self.cleaned_data.get("payload") or {},
        )


class SOSReportForm(RTLModelForm):
    class Meta:
        model = SOSReport
        fields = ["event", "category", "priority", "location", "assigned_to", "status", "description", "resolution_notes"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "resolution_notes": forms.Textarea(attrs={"rows": 3})}


class CertificateTemplateForm(RTLModelForm):
    class Meta:
        model = CertificateTemplate
        fields = ["event", "name", "certificate_type", "title", "body_template", "signature_name", "signature_title", "include_sponsor_logos", "active"]


class BulkCertificateIssueForm(forms.Form):
    event = forms.ModelChoiceField(label="الفعالية", queryset=Event.objects.none())
    certificate_type = forms.CharField(label="نوع الشهادة", max_length=80, initial="attendance")
    statuses = forms.MultipleChoiceField(
        label="حالات المشاركين",
        choices=[
            (RegistrationStatus.APPROVED, "مقبول"),
            (RegistrationStatus.CHECKED_IN, "سجل حضور"),
            (RegistrationStatus.CHECKED_OUT, "سجل خروج"),
            (RegistrationStatus.ATTENDED, "حضر"),
        ],
        required=False,
    )
    send_email = forms.BooleanField(label="إرسال بريد بعد الإصدار", required=False)

    def __init__(self, *args, events=None, **kwargs):
        super().__init__(*args, **kwargs)
        if events is not None:
            self.fields["event"].queryset = events
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"


class VIPInvitationForm(RTLModelForm):
    class Meta:
        model = VIPInvitation
        fields = ["event", "name", "title", "email", "phone", "reserved_seat", "special_entrance", "companions", "protocol_notes", "expected_arrival", "host", "car_number", "seating_area", "has_speech", "needs_certificate_or_trophy", "status"]
        widgets = {"expected_arrival": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class SpeakerForm(RTLModelForm):
    class Meta:
        model = Speaker
        fields = ["event", "name", "title", "bio", "photo", "email", "phone", "arrival_time", "technical_needs", "presentation_file", "public_profile", "publishing_consent"]
        widgets = {"arrival_time": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class SponsorForm(RTLModelForm):
    class Meta:
        model = Sponsor
        fields = ["event", "name", "logo", "website", "level", "sponsorship_value", "benefits", "show_on_site", "show_on_certificate", "show_on_display", "booth", "representative_name"]


class ViolationTypeForm(RTLModelForm):
    class Meta:
        model = ViolationType
        fields = ["event", "name", "default_action", "blocks_certificate", "points_penalty"]


class IncidentViolationForm(RTLModelForm):
    class Meta:
        model = IncidentViolation
        fields = ["event", "participant", "violation_type", "location", "action_taken", "notes", "status", "appeal_notes", "appeal_result", "attachment"]


class MediaItemForm(RTLModelForm):
    class Meta:
        model = MediaItem
        fields = ["event", "type", "title", "body", "file", "external_url", "published"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}


class SurveyForm(RTLModelForm):
    class Meta:
        model = Survey
        fields = ["event", "workshop", "title", "active", "certificate_required"]


class SurveyQuestionForm(RTLModelForm):
    class Meta:
        model = SurveyQuestion
        fields = ["survey", "text", "question_type", "options", "required", "order"]


class PublicSurveyResponseForm(forms.Form):
    tracking_code = forms.CharField(label="كود المتابعة", max_length=80)

    def __init__(self, *args, survey, **kwargs):
        self.survey = survey
        super().__init__(*args, **kwargs)
        for question in survey.questions.all():
            field_name = f"q_{question.id}"
            kwargs = {"label": question.text, "required": question.required}
            if question.question_type == SurveyQuestion.QuestionType.STARS:
                self.fields[field_name] = forms.IntegerField(min_value=1, max_value=5, **kwargs)
            elif question.question_type == SurveyQuestion.QuestionType.NPS:
                self.fields[field_name] = forms.IntegerField(min_value=0, max_value=10, **kwargs)
            elif question.question_type == SurveyQuestion.QuestionType.CHOICE:
                choices = [(option, option) for option in question.options]
                self.fields[field_name] = forms.ChoiceField(choices=choices, **kwargs)
            elif question.question_type == SurveyQuestion.QuestionType.EMOJI:
                self.fields[field_name] = forms.ChoiceField(choices=[("😀", "😀"), ("🙂", "🙂"), ("😐", "😐"), ("🙁", "🙁")], **kwargs)
            else:
                self.fields[field_name] = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
            field.widget.attrs["dir"] = "rtl"

    def save(self):
        participant = Participant.objects.filter(
            event=self.survey.event,
            tracking_code=self.cleaned_data["tracking_code"],
            is_deleted=False,
        ).first()
        if not participant:
            raise ValidationError("كود المتابعة غير صحيح.")
        answers = {}
        numeric_scores = []
        for question in self.survey.questions.all():
            value = self.cleaned_data.get(f"q_{question.id}")
            answers[str(question.id)] = {"question": question.text, "answer": value}
            if question.question_type in {SurveyQuestion.QuestionType.STARS, SurveyQuestion.QuestionType.NPS} and value not in {None, ""}:
                numeric_scores.append(int(value))
        satisfaction = round(sum(numeric_scores) / len(numeric_scores)) if numeric_scores else 0
        response, _ = SurveyResponse.objects.update_or_create(
            survey=self.survey,
            participant=participant,
            defaults={"answers": answers, "satisfaction_score": satisfaction},
        )
        return response


class TicketTypeForm(RTLModelForm):
    class Meta:
        model = TicketType
        fields = ["event", "name", "price", "currency", "capacity", "early_bird_until", "active"]
        widgets = {"early_bird_until": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class CouponForm(RTLModelForm):
    class Meta:
        model = Coupon
        fields = ["event", "code", "discount_type", "value", "max_uses", "active", "valid_until"]
        labels = {"event": "الفعالية", "code": "الكود", "discount_type": "نوع الخصم", "value": "قيمة الخصم", "max_uses": "حد الاستخدام", "active": "مفعل", "valid_until": "صالح حتى"}
        widgets = {"valid_until": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class ExpenseForm(RTLModelForm):
    class Meta:
        model = Expense
        fields = ["event", "category", "description", "amount", "paid_at"]
        widgets = {"paid_at": forms.DateInput(attrs={"type": "date"})}


class InvoiceForm(RTLModelForm):
    class Meta:
        model = Invoice
        fields = ["event", "ticket", "participant", "subtotal", "discount", "total", "paid_amount", "status", "due_at", "notes"]
        labels = {
            "event": "الفعالية",
            "ticket": "التذكرة",
            "participant": "المشارك",
            "subtotal": "الإجمالي قبل الخصم",
            "discount": "الخصم",
            "total": "الإجمالي",
            "paid_amount": "المدفوع",
            "status": "الحالة",
            "due_at": "تاريخ الاستحقاق",
            "notes": "ملاحظات",
        }
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}), "notes": forms.Textarea(attrs={"rows": 3})}


class RefundForm(RTLModelForm):
    class Meta:
        model = Refund
        fields = ["event", "ticket", "participant", "amount", "reason", "status"]
        labels = {"event": "الفعالية", "ticket": "التذكرة", "participant": "المشارك", "amount": "المبلغ", "reason": "السبب", "status": "الحالة"}


class TicketIssueForm(forms.Form):
    event = forms.ModelChoiceField(label="الفعالية", queryset=Event.objects.none())
    participant_code = forms.CharField(label="كود المشارك", max_length=80)
    ticket_type = forms.ModelChoiceField(label="نوع التذكرة", queryset=TicketType.objects.none())
    coupon_code = forms.CharField(label="كود خصم", max_length=60, required=False)

    def __init__(self, *args, events=None, **kwargs):
        super().__init__(*args, **kwargs)
        if events is not None:
            self.fields["event"].queryset = events
            self.fields["ticket_type"].queryset = TicketType.objects.filter(event__in=events, active=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"

    def save(self):
        event = self.cleaned_data["event"]
        participant = Participant.objects.filter(event=event, tracking_code=self.cleaned_data["participant_code"], is_deleted=False).first()
        if not participant:
            raise ValidationError("كود المشارك غير صحيح.")
        ticket_type = self.cleaned_data["ticket_type"]
        if ticket_type.event_id != event.id:
            raise ValidationError("نوع التذكرة لا يتبع نفس الفعالية.")
        amount = ticket_type.price
        coupon_code = self.cleaned_data.get("coupon_code", "").strip()
        if coupon_code:
            coupon = Coupon.objects.filter(event=event, code__iexact=coupon_code, active=True).first()
            if not coupon:
                raise ValidationError("كود الخصم غير صالح.")
            if coupon.valid_until and coupon.valid_until < services.timezone.now():
                raise ValidationError("كود الخصم منتهي.")
            if coupon.max_uses and coupon.used_count >= coupon.max_uses:
                raise ValidationError("تم استهلاك كود الخصم.")
            if coupon.discount_type == Coupon.DiscountType.PERCENT:
                amount = max(amount - (amount * coupon.value / 100), 0)
            else:
                amount = max(amount - coupon.value, 0)
        else:
            coupon = None
        ticket, created = Ticket.objects.get_or_create(
            event=event,
            participant=participant,
            defaults={"ticket_type": ticket_type, "amount": amount, "coupon_code": coupon_code, "payment_status": Ticket.PaymentStatus.FREE if amount == 0 else Ticket.PaymentStatus.PENDING},
        )
        if created and coupon:
            coupon.used_count += 1
            coupon.save(update_fields=["used_count", "updated_at"])
        if ticket.invoice_number == "":
            invoice, _ = Invoice.objects.get_or_create(
                ticket=ticket,
                defaults={
                    "event": event,
                    "participant": participant,
                    "subtotal": ticket_type.price,
                    "discount": ticket_type.price - amount,
                    "total": amount,
                    "paid_amount": 0,
                    "status": Invoice.Status.PAID if amount == 0 else Invoice.Status.ISSUED,
                },
            )
            ticket.invoice_number = invoice.invoice_number
            ticket.receipt_number = f"RCT-{ticket.qr_code.split('-')[-1]}"
            ticket.save(update_fields=["invoice_number", "receipt_number", "updated_at"])
        return ticket


class AppVersionForm(RTLModelForm):
    class Meta:
        model = AppVersion
        fields = ["platform", "version", "apk_url", "force_update", "update_message", "min_supported_version", "release_notes", "active", "released_at"]
        widgets = {"released_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class SubscriptionPlanForm(RTLModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = ["name", "max_events", "max_participants", "monthly_price", "features", "active"]


class OrganizationSubscriptionForm(RTLModelForm):
    class Meta:
        model = OrganizationSubscription
        fields = ["organization", "plan", "starts_at", "ends_at", "active", "email_quota_used", "push_quota_used", "certificate_quota_used"]
        widgets = {"starts_at": forms.DateInput(attrs={"type": "date"}), "ends_at": forms.DateInput(attrs={"type": "date"})}


class BackupJobForm(RTLModelForm):
    class Meta:
        model = BackupJob
        fields = ["organization", "job_type"]
