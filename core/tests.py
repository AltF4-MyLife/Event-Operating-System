from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from . import services
from .models import (
    AppVersion,
    BackupJob,
    Badge,
    Broadcast,
    Certificate,
    Coupon,
    EducationAdministration,
    EmailLog,
    EmailTemplate,
    Event,
    EventDay,
    CheckInLog,
    Hall,
    IncidentViolation,
    Invoice,
    MediaItem,
    NotificationLog,
    Organization,
    Participant,
    ParticipantBadge,
    ParticipantGroup,
    PointRule,
    PointTransaction,
    ReportSnapshot,
    RegistrationStatus,
    Refund,
    Role,
    School,
    Session,
    SubscriptionPlan,
    Survey,
    SurveyQuestion,
    SurveyResponse,
    Ticket,
    TicketType,
    Track,
    UploadedDocument,
    UserProfile,
    ViolationType,
    Volunteer,
    VolunteerShift,
    Workshop,
    WorkshopRegistration,
    StudentNote,
)


class EventOSTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        cls.staff = User.objects.create_user("staff", "staff@example.com", "pass12345", is_staff=True)
        cls.org = Organization.objects.create(name="جهة اختبار", slug="test-org")
        cls.event = Event.objects.create(
            organization=cls.org,
            name="فعالية اختبار",
            slug="test-event",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=2),
            capacity=100,
        )
        services.ensure_default_modules(cls.event, actor=cls.admin)
        services.ensure_registration_form(cls.event)
        UserProfile.objects.update_or_create(user=cls.staff, defaults={"role": Role.CHECKIN_STAFF, "organization": cls.org})
        cls.staff.profile.assigned_events.add(cls.event)
        cls.hall = Hall.objects.create(event=cls.event, name="قاعة اختبار", capacity=30)


class PageSmokeTests(EventOSTestCase):
    def test_core_public_and_dashboard_pages_render(self):
        participant = Participant.objects.create(
            event=self.event,
            full_name="مشارك Smoke",
            phone="01090000000",
            email="smoke@example.com",
            status=RegistrationStatus.APPROVED,
        )
        certificate = services.issue_certificate(participant, actor=self.admin)
        self.client.login(username="admin", password="pass12345")

        routes = [
            reverse("public-home"),
            reverse("certificate-verify"),
            reverse("dashboard"),
            reverse("admin-organizations"),
            reverse("admin-users"),
            reverse("admin-education"),
            reverse("admin-events"),
            reverse("admin-venues"),
            reverse("admin-sessions"),
            reverse("admin-registrations"),
            reverse("admin-workshops"),
            reverse("admin-volunteers"),
            reverse("admin-student-notes"),
            reverse("admin-gamification"),
            reverse("admin-certificates"),
            reverse("admin-communications"),
            reverse("admin-crisis"),
            reverse("admin-support"),
            reverse("admin-people"),
            reverse("admin-feedback"),
            reverse("admin-media"),
            reverse("admin-finance"),
            reverse("admin-platform"),
            reverse("admin-violations"),
            reverse("admin-reports"),
            reverse("public-event", args=[self.event.slug]),
            reverse("public-register", args=[self.event.slug]),
            reverse("registration-status", args=[self.event.slug]),
            reverse("registration-status-code", args=[self.event.slug, participant.tracking_code]),
            reverse("ticket", args=[self.event.slug, participant.tracking_code]),
            reverse("public-schedule", args=[self.event.slug]),
            reverse("public-workshops", args=[self.event.slug]),
            reverse("public-leaderboard", args=[self.event.slug]),
            reverse("public-certificates", args=[self.event.slug]),
            reverse("public-feedback", args=[self.event.slug]),
            reverse("public-media", args=[self.event.slug]),
            reverse("public-support", args=[self.event.slug]),
            reverse("public-support-status", args=[self.event.slug]),
            reverse("public-display", args=[self.event.slug]),
            reverse("admin-event-modules", args=[self.event.id]),
            reverse("admin-registration-form", args=[self.event.id]),
            reverse("admin-event-reports", args=[self.event.id]),
            reverse("admin-event-final-report", args=[self.event.id]),
            reverse("admin-participant-detail", args=[participant.id]),
            reverse("certificate-verify-code", args=[certificate.verification_code]),
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertLess(self.client.get(route).status_code, 400)


class RegistrationAndCheckinTests(EventOSTestCase):
    def test_public_registration_review_and_duplicate_checkin(self):
        response = self.client.post(
            reverse("public-register", args=[self.event.slug]),
            {
                "registration_type": Participant.RegistrationType.STUDENT,
                "full_name": "طالب اختبار",
                "phone": "01012345678",
                "email": "student@example.com",
                "field_terms": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        participant = Participant.objects.get(phone="01012345678")
        self.assertIn(participant.status, {RegistrationStatus.APPROVED, RegistrationStatus.PENDING_REVIEW, RegistrationStatus.SUBMITTED})

        duplicate = self.client.post(
            reverse("public-register", args=[self.event.slug]),
            {
                "registration_type": Participant.RegistrationType.STUDENT,
                "full_name": "طالب مكرر",
                "phone": "01012345678",
                "email": "student@example.com",
                "field_terms": "on",
            },
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(Participant.objects.filter(phone="01012345678").count(), 1)

        services.review_participant(participant, "approve", actor=self.admin)
        services.perform_checkin(self.event, participant.qr_code, actor=self.staff, gate="A", device="test")
        participant.refresh_from_db()
        self.assertEqual(participant.status, RegistrationStatus.CHECKED_IN)
        with self.assertRaises(ValidationError):
            services.perform_checkin(self.event, participant.qr_code, actor=self.staff, gate="A", device="test")

    def test_export_excel_and_jwt_api(self):
        Participant.objects.create(event=self.event, full_name="مشارك API", phone="01022222222", status=RegistrationStatus.APPROVED)
        self.client.login(username="admin", password="pass12345")
        export_response = self.client.get(reverse("admin-event-participants-export", args=[self.event.id]))
        self.assertEqual(export_response.status_code, 200)
        self.assertIn("spreadsheetml", export_response["Content-Type"])

        token_response = self.client.post(reverse("token_obtain_pair"), {"username": "admin", "password": "pass12345"})
        self.assertEqual(token_response.status_code, 200)
        access = token_response.json()["access"]
        api_response = self.client.get("/api/participants/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(api_response.status_code, 200)

    def test_sensitive_api_requires_specific_capability(self):
        Participant.objects.create(event=self.event, full_name="مشارك صلاحيات", phone="01024444444", status=RegistrationStatus.APPROVED)
        token_response = self.client.post(reverse("token_obtain_pair"), {"username": "staff", "password": "pass12345"})
        access = token_response.json()["access"]
        auth = {"HTTP_AUTHORIZATION": f"Bearer {access}"}

        self.assertEqual(self.client.get("/api/participants/", **auth).status_code, 200)
        self.assertEqual(self.client.get("/api/tickets/", **auth).status_code, 403)
        self.assertEqual(self.client.get("/api/app-versions/", **auth).status_code, 403)
        self.assertEqual(self.client.get("/api/audit-logs/", **auth).status_code, 403)

    def test_dashboard_checkin_and_checkout_actions(self):
        participant = Participant.objects.create(event=self.event, full_name="حضور وخروج", phone="01023232323", status=RegistrationStatus.APPROVED)
        self.client.login(username="admin", password="pass12345")
        checkin_response = self.client.post(
            reverse("admin-checkin", args=[self.event.id]),
            {"action": CheckInLog.Action.CHECKIN, "code": participant.qr_code, "gate": "A", "device": "unit-test"},
        )
        self.assertEqual(checkin_response.status_code, 302)
        participant.refresh_from_db()
        self.assertEqual(participant.status, RegistrationStatus.CHECKED_IN)

        checkout_response = self.client.post(
            reverse("admin-checkin", args=[self.event.id]),
            {"action": CheckInLog.Action.CHECKOUT, "code": participant.qr_code, "gate": "A", "device": "unit-test"},
        )
        self.assertEqual(checkout_response.status_code, 302)
        participant.refresh_from_db()
        self.assertEqual(participant.status, RegistrationStatus.CHECKED_OUT)
        self.assertTrue(CheckInLog.objects.filter(participant=participant, action=CheckInLog.Action.CHECKOUT, success=True).exists())


class WorkshopAndCertificateTests(EventOSTestCase):
    def test_workshop_conflict_is_blocked(self):
        participant = Participant.objects.create(event=self.event, full_name="متدرب", phone="01033333333", status=RegistrationStatus.APPROVED)
        starts = timezone.now() + timedelta(days=1, hours=2)
        first = Workshop.objects.create(event=self.event, title="ورشة أولى", hall=self.hall, starts_at=starts, ends_at=starts + timedelta(hours=2), capacity=5)
        second = Workshop.objects.create(event=self.event, title="ورشة ثانية", hall=self.hall, starts_at=starts + timedelta(hours=1), ends_at=starts + timedelta(hours=3), capacity=5)
        services.enroll_workshop(first, participant, actor=self.admin)
        with self.assertRaises(ValidationError):
            services.enroll_workshop(second, participant, actor=self.admin)

    def test_certificate_blocked_by_violation_then_issued(self):
        participant = Participant.objects.create(event=self.event, full_name="مستحق شهادة", phone="01044444444", status=RegistrationStatus.APPROVED)
        violation_type = ViolationType.objects.create(event=self.event, name="مانعة شهادة", blocks_certificate=True)
        violation = services.record_violation(participant, violation_type, reported_by=self.admin)
        participant.refresh_from_db()
        self.assertTrue(participant.certificate_blocked)
        with self.assertRaises(ValidationError):
            services.issue_certificate(participant, actor=self.admin)

        violation.status = IncidentViolation.Status.RESOLVED
        violation.save()
        participant.certificate_blocked = False
        participant.certificate_block_reason = ""
        participant.status = RegistrationStatus.APPROVED
        participant.save()
        certificate = services.issue_certificate(participant, actor=self.admin)
        self.assertTrue(certificate.verification_code)
        self.assertGreater(len(services.render_certificate_pdf(certificate)), 100)


class AdminOperationsTests(EventOSTestCase):
    def workbook_upload(self, rows):
        workbook = Workbook()
        sheet = workbook.active
        for row in rows:
            sheet.append(row)
        out = BytesIO()
        workbook.save(out)
        out.seek(0)
        return SimpleUploadedFile("participants.xlsx", out.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_excel_import_and_bulk_review_dashboard(self):
        self.client.login(username="admin", password="pass12345")
        upload = self.workbook_upload([
            ["full_name", "phone", "email", "governorate"],
            ["مستورد واحد", "01055555555", "imported@example.com", "القاهرة"],
        ])
        response = self.client.post(
            reverse("admin-event-registrations", args=[self.event.id]),
            {
                "form_kind": "import",
                "import-default_status": RegistrationStatus.SUBMITTED,
                "import-file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        participant = Participant.objects.get(phone="01055555555")
        self.assertEqual(participant.status, RegistrationStatus.SUBMITTED)

        response = self.client.post(
            reverse("admin-event-registrations", args=[self.event.id]),
            {
                "form_kind": "bulk",
                "selected": [str(participant.id)],
                "bulk-action": "approve",
                "bulk-note": "قبول جماعي",
            },
        )
        self.assertEqual(response.status_code, 302)
        participant.refresh_from_db()
        self.assertEqual(participant.status, RegistrationStatus.APPROVED)

    def test_workshop_attendance_and_certificate_email_api(self):
        participant = Participant.objects.create(
            event=self.event,
            full_name="حاضر ورشة",
            phone="01066666666",
            email="workshop@example.com",
            status=RegistrationStatus.APPROVED,
        )
        starts = timezone.now() + timedelta(days=1, hours=2)
        workshop = Workshop.objects.create(event=self.event, title="ورشة حضور", hall=self.hall, starts_at=starts, ends_at=starts + timedelta(hours=2), capacity=10, points=7)
        services.enroll_workshop(workshop, participant, actor=self.admin)

        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("admin-event-workshops", args=[self.event.id]),
            {
                "form_kind": "attendance",
                "workshop": workshop.id,
                "code": participant.qr_code,
                "gate": "معمل",
                "device": "unit-test",
            },
        )
        self.assertEqual(response.status_code, 302)
        registration = WorkshopRegistration.objects.get(workshop=workshop, participant=participant)
        self.assertEqual(registration.status, WorkshopRegistration.Status.ATTENDED)
        self.assertEqual(services.participant_points_total(participant), 7)

        certificate = services.issue_certificate(participant, actor=self.admin)
        token_response = self.client.post(reverse("token_obtain_pair"), {"username": "admin", "password": "pass12345"})
        access = token_response.json()["access"]
        api_response = self.client.post(f"/api/certificates/{certificate.id}/send_email/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(api_response.status_code, 200)
        certificate.refresh_from_db()
        self.assertEqual(certificate.sent_count, 1)

    def test_bulk_certificate_issue_send_cancel_and_reissue(self):
        participants = [
            Participant.objects.create(event=self.event, full_name="شهادة جماعية 1", phone="01015151515", email="bulk1@example.com", status=RegistrationStatus.APPROVED),
            Participant.objects.create(event=self.event, full_name="شهادة جماعية 2", phone="01016161616", email="bulk2@example.com", status=RegistrationStatus.APPROVED),
        ]
        self.client.login(username="admin", password="pass12345")
        issue_response = self.client.post(
            reverse("admin-event-certificates", args=[self.event.id]),
            {
                "form_kind": "bulk_issue",
                "bulk-event": self.event.id,
                "bulk-certificate_type": "attendance",
                "bulk-statuses": [RegistrationStatus.APPROVED],
                "bulk-send_email": "on",
            },
        )
        self.assertEqual(issue_response.status_code, 302)
        self.assertEqual(Certificate.objects.filter(event=self.event, participant__in=participants, status=Certificate.Status.ISSUED).count(), 2)
        first = Certificate.objects.get(participant=participants[0])
        self.assertEqual(first.sent_count, 1)

        cancel_response = self.client.post(reverse("admin-event-certificates", args=[self.event.id]), {"form_kind": "cancel_certificate", "certificate": first.id})
        self.assertEqual(cancel_response.status_code, 302)
        first.refresh_from_db()
        self.assertEqual(first.status, Certificate.Status.CANCELLED)

        reissue_response = self.client.post(reverse("admin-event-certificates", args=[self.event.id]), {"form_kind": "reissue_certificate", "certificate": first.id})
        self.assertEqual(reissue_response.status_code, 302)
        first.refresh_from_db()
        self.assertEqual(first.status, Certificate.Status.ISSUED)

        send_response = self.client.post(
            reverse("admin-event-certificates", args=[self.event.id]),
            {
                "form_kind": "bulk_send",
                "bulk-event": self.event.id,
                "bulk-certificate_type": "attendance",
                "bulk-statuses": [RegistrationStatus.APPROVED],
            },
        )
        self.assertEqual(send_response.status_code, 302)
        first.refresh_from_db()
        self.assertGreaterEqual(first.sent_count, 2)

    def test_participant_detail_management_page(self):
        participant = Participant.objects.create(
            event=self.event,
            full_name="ملف مشارك",
            phone="01017171717",
            email="profile@example.com",
            status=RegistrationStatus.SUBMITTED,
        )
        self.client.login(username="admin", password="pass12345")
        detail_url = reverse("admin-participant-detail", args=[participant.id])

        update_response = self.client.post(
            detail_url,
            {
                "form_kind": "update",
                "participant-registration_type": Participant.RegistrationType.STUDENT,
                "participant-full_name": "ملف مشارك محدث",
                "participant-phone": "01017171717",
                "participant-email": "profile-updated@example.com",
                "participant-governorate": "القاهرة",
                "participant-status": RegistrationStatus.APPROVED,
                "participant-review_notes": "تم تحديث الملف",
            },
        )
        self.assertEqual(update_response.status_code, 302)
        participant.refresh_from_db()
        self.assertEqual(participant.full_name, "ملف مشارك محدث")
        self.assertEqual(participant.status, RegistrationStatus.APPROVED)

        note_response = self.client.post(
            detail_url,
            {
                "form_kind": "note",
                "note-participant": participant.id,
                "note-category": "academic",
                "note-note": "ملاحظة من صفحة الملف",
                "note-visible_to_student": "on",
            },
        )
        self.assertEqual(note_response.status_code, 302)
        self.assertTrue(StudentNote.objects.filter(participant=participant, category="academic").exists())

        upload = SimpleUploadedFile("proof.txt", b"bad", content_type="text/plain")
        document_response = self.client.post(
            detail_url,
            {"form_kind": "document", "document-label": "إثبات", "document-file": upload, "document-verified": "on"},
        )
        self.assertEqual(document_response.status_code, 200)

        valid_upload = SimpleUploadedFile("proof.pdf", b"%PDF-1.4\n%", content_type="application/pdf")
        document_response = self.client.post(
            detail_url,
            {"form_kind": "document", "document-label": "إثبات", "document-file": valid_upload, "document-verified": "on"},
        )
        self.assertEqual(document_response.status_code, 302)
        self.assertTrue(UploadedDocument.objects.filter(participant=participant, label="إثبات", verified=True).exists())

        points_response = self.client.post(
            detail_url,
            {
                "form_kind": "points",
                "points-event": self.event.id,
                "points-participant": participant.id,
                "points-value": "12",
                "points-reason": "تميز من ملف المشارك",
            },
        )
        self.assertEqual(points_response.status_code, 302)
        self.assertEqual(services.participant_points_total(participant), 12)

        certificate_response = self.client.post(detail_url, {"form_kind": "issue_certificate"})
        self.assertEqual(certificate_response.status_code, 302)
        self.assertTrue(Certificate.objects.filter(participant=participant, status=Certificate.Status.ISSUED).exists())

        page_response = self.client.get(detail_url)
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "ملف المشارك")
        self.assertContains(page_response, "ملف مشارك محدث")


class VenueScheduleVolunteerTests(EventOSTestCase):
    def test_venues_and_sessions_dashboard(self):
        self.client.login(username="admin", password="pass12345")
        day_date = (timezone.now() + timedelta(days=1)).date()
        day_response = self.client.post(
            reverse("admin-event-venues", args=[self.event.id]),
            {
                "form_kind": "day",
                "day-event": self.event.id,
                "day-name": "اليوم الأول",
                "day-date": day_date.strftime("%Y-%m-%d"),
                "day-order": "1",
            },
        )
        self.assertEqual(day_response.status_code, 302)
        day = EventDay.objects.get(event=self.event, name="اليوم الأول")

        track_response = self.client.post(
            reverse("admin-event-venues", args=[self.event.id]),
            {
                "form_kind": "track",
                "track-event": self.event.id,
                "track-name": "مسار الابتكار",
                "track-description": "جلسات تقنية",
                "track-color": "#0f766e",
            },
        )
        self.assertEqual(track_response.status_code, 302)
        track = Track.objects.get(event=self.event, name="مسار الابتكار")

        hall_response = self.client.post(
            reverse("admin-event-venues", args=[self.event.id]),
            {
                "form_kind": "hall",
                "hall-event": self.event.id,
                "hall-name": "قاعة رئيسية",
                "hall-capacity": "120",
                "hall-equipment": "شاشة وصوت",
                "hall-area_type": "main",
                "hall-is_active": "on",
            },
        )
        self.assertEqual(hall_response.status_code, 302)
        hall = Hall.objects.get(event=self.event, name="قاعة رئيسية")

        starts = timezone.now() + timedelta(days=1, hours=3)
        session_response = self.client.post(
            reverse("admin-event-sessions", args=[self.event.id]),
            {
                "event": self.event.id,
                "day": day.id,
                "track": track.id,
                "hall": hall.id,
                "title": "جلسة الافتتاح",
                "description": "تعريف بالبرنامج",
                "starts_at": starts.strftime("%Y-%m-%dT%H:%M"),
                "ends_at": (starts + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                "status": Session.Status.NOT_STARTED,
                "is_public": "on",
            },
        )
        self.assertEqual(session_response.status_code, 302)
        self.assertTrue(Session.objects.filter(event=self.event, title="جلسة الافتتاح", hall=hall).exists())
        self.assertEqual(self.client.get(reverse("admin-venues")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin-sessions")).status_code, 200)

    def test_volunteer_shift_and_student_note_dashboard(self):
        self.client.login(username="admin", password="pass12345")
        volunteer_participant = Participant.objects.create(
            event=self.event,
            full_name="متطوع اختبار",
            phone="01011112222",
            registration_type=Participant.RegistrationType.VOLUNTEER,
            status=RegistrationStatus.APPROVED,
        )
        volunteer_response = self.client.post(
            reverse("admin-event-volunteers", args=[self.event.id]),
            {
                "form_kind": "volunteer",
                "volunteer-participant": volunteer_participant.id,
                "volunteer-role": Volunteer.RoleChoice.CHECKIN,
                "volunteer-area": "البوابة الرئيسية",
                "volunteer-accepted": "on",
                "volunteer-performance_score": "4",
                "volunteer-notes": "جاهز للتوزيع",
            },
        )
        self.assertEqual(volunteer_response.status_code, 302)
        volunteer = Volunteer.objects.get(participant=volunteer_participant)

        starts = timezone.now() + timedelta(days=1, hours=2)
        shift_response = self.client.post(
            reverse("admin-event-volunteers", args=[self.event.id]),
            {
                "form_kind": "shift",
                "shift-volunteer": volunteer.id,
                "shift-shift_type": VolunteerShift.ShiftType.MORNING,
                "shift-starts_at": starts.strftime("%Y-%m-%dT%H:%M"),
                "shift-ends_at": (starts + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M"),
                "shift-location": "الاستقبال",
                "shift-status": "scheduled",
            },
        )
        self.assertEqual(shift_response.status_code, 302)
        self.assertTrue(VolunteerShift.objects.filter(volunteer=volunteer, location="الاستقبال").exists())

        student = Participant.objects.create(event=self.event, full_name="طالب بملاحظة", phone="01011113333", status=RegistrationStatus.APPROVED)
        note_response = self.client.post(
            reverse("admin-event-student-notes", args=[self.event.id]),
            {
                "participant": student.id,
                "category": "followup",
                "note": "يحتاج متابعة بعد الورشة.",
                "visible_to_student": "on",
            },
        )
        self.assertEqual(note_response.status_code, 302)
        note = StudentNote.objects.get(participant=student)
        self.assertEqual(note.author, self.admin)
        self.assertTrue(note.visible_to_student)
        self.assertEqual(self.client.get(reverse("admin-volunteers")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin-student-notes")).status_code, 200)


class GamificationTests(EventOSTestCase):
    def test_points_badges_and_public_leaderboard(self):
        self.client.login(username="admin", password="pass12345")
        participant = Participant.objects.create(event=self.event, full_name="طالب نقاط", phone="01012121212", status=RegistrationStatus.APPROVED)

        rule_response = self.client.post(
            reverse("admin-event-gamification", args=[self.event.id]),
            {
                "form_kind": "rule",
                "rule-event": self.event.id,
                "rule-name": "نقاط حضور",
                "rule-trigger": "checkin",
                "rule-value": "10",
                "rule-enabled": "on",
            },
        )
        self.assertEqual(rule_response.status_code, 302)
        self.assertTrue(PointRule.objects.filter(event=self.event, name="نقاط حضور", value=10).exists())

        badge_response = self.client.post(
            reverse("admin-event-gamification", args=[self.event.id]),
            {
                "form_kind": "badge",
                "badge-event": self.event.id,
                "badge-name": "نجم النقاط",
                "badge-description": "وسام تلقائي",
                "badge-icon": "star",
                "badge-points_required": "20",
                "badge-attendance_percent_required": "0",
                "badge-auto_award": "on",
            },
        )
        self.assertEqual(badge_response.status_code, 302)
        badge = Badge.objects.get(event=self.event, name="نجم النقاط")

        points_response = self.client.post(
            reverse("admin-event-gamification", args=[self.event.id]),
            {
                "form_kind": "points",
                "points-event": self.event.id,
                "points-participant": participant.id,
                "points-value": "25",
                "points-reason": "تميز في النشاط",
            },
        )
        self.assertEqual(points_response.status_code, 302)
        self.assertEqual(services.participant_points_total(participant), 25)
        self.assertTrue(PointTransaction.objects.filter(participant=participant, value=25, source="manual").exists())
        self.assertTrue(ParticipantBadge.objects.filter(participant=participant, badge=badge).exists())

        manual_badge = Badge.objects.create(event=self.event, name="وسام يدوي", icon="award")
        award_response = self.client.post(
            reverse("admin-event-gamification", args=[self.event.id]),
            {
                "form_kind": "award_badge",
                "award_badge-event": self.event.id,
                "award_badge-participant": participant.id,
                "award_badge-badge": manual_badge.id,
                "award_badge-reason": "مشاركة مميزة",
            },
        )
        self.assertEqual(award_response.status_code, 302)
        self.assertTrue(ParticipantBadge.objects.filter(participant=participant, badge=manual_badge).exists())

        admin_response = self.client.get(reverse("admin-event-gamification", args=[self.event.id]))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "طالب نقاط")
        public_response = self.client.get(reverse("public-leaderboard", args=[self.event.slug]))
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, "طالب نقاط")


class CommunicationsTests(EventOSTestCase):
    def test_email_templates_push_broadcast_and_resend(self):
        self.client.login(username="admin", password="pass12345")
        participant = Participant.objects.create(
            event=self.event,
            full_name="مشارك بريد",
            phone="01013131313",
            email="mail-participant@example.com",
            status=RegistrationStatus.APPROVED,
        )

        template_response = self.client.post(
            reverse("admin-communications"),
            {
                "form_kind": "template",
                "template-event": self.event.id,
                "template-key": "acceptance",
                "template-subject": "أهلًا {participant}",
                "template-body": "تم قبولك في {event}. كودك {tracking_code}",
                "template-active": "on",
            },
        )
        self.assertEqual(template_response.status_code, 302)
        template = EmailTemplate.objects.get(event=self.event, key="acceptance")

        email_response = self.client.post(
            reverse("admin-communications"),
            {
                "form_kind": "email",
                "email-event": self.event.id,
                "email-participant": participant.id,
                "email-template": template.id,
            },
        )
        self.assertEqual(email_response.status_code, 302)
        email_log = EmailLog.objects.get(participant=participant, subject=f"أهلًا {participant.full_name}")
        self.assertEqual(email_log.status, EmailLog.Status.MOCKED)
        self.assertIn(participant.tracking_code, email_log.body)

        push_response = self.client.post(
            reverse("admin-communications"),
            {
                "form_kind": "push",
                "push-event": self.event.id,
                "push-audience": "students",
                "push-title": "تنبيه اختبار",
                "push-body": "رسالة آمنة",
                "push-payload": '{"screen": "home", "email": "hidden@example.com"}',
            },
        )
        self.assertEqual(push_response.status_code, 302)
        notification = NotificationLog.objects.get(event=self.event, title="تنبيه اختبار")
        self.assertEqual(notification.status, "mocked")
        self.assertNotIn("email", notification.safe_payload)

        broadcast_response = self.client.post(
            reverse("admin-communications"),
            {
                "form_kind": "broadcast",
                "broadcast-event": self.event.id,
                "broadcast-audience": "approved",
                "broadcast-channel": Broadcast.Channel.PUSH,
                "broadcast-title": "Broadcast اختبار",
                "broadcast-message": "رسالة جماعية",
                "send_now": "1",
            },
        )
        self.assertEqual(broadcast_response.status_code, 302)
        broadcast = Broadcast.objects.get(event=self.event, title="Broadcast اختبار")
        self.assertEqual(broadcast.status, "sent")

        before = EmailLog.objects.count()
        resend_response = self.client.post(reverse("admin-communications"), {"form_kind": "resend_email", "email_log": email_log.id})
        self.assertEqual(resend_response.status_code, 302)
        self.assertEqual(EmailLog.objects.count(), before + 1)

        page_response = self.client.get(reverse("admin-communications"))
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "مركز الاتصالات")


class FeedbackMediaFinanceMobileTests(EventOSTestCase):
    def test_feedback_required_for_certificate_and_public_submission(self):
        participant = Participant.objects.create(
            event=self.event,
            full_name="طالب تقييم",
            phone="01077777777",
            email="feedback@example.com",
            status=RegistrationStatus.APPROVED,
        )
        survey = Survey.objects.create(event=self.event, title="تقييم الفعالية", active=True, certificate_required=True)
        question = SurveyQuestion.objects.create(survey=survey, text="ما تقييمك؟", question_type=SurveyQuestion.QuestionType.STARS, order=1)

        eligible, reason = services.certificate_eligibility(participant)
        self.assertFalse(eligible)
        self.assertIn("التقييم", reason)

        response = self.client.post(
            reverse("public-feedback", args=[self.event.slug]) + f"?survey={survey.id}",
            {"tracking_code": participant.tracking_code, f"q_{question.id}": "5"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SurveyResponse.objects.filter(survey=survey, participant=participant).exists())
        eligible, _ = services.certificate_eligibility(participant)
        self.assertTrue(eligible)

    def test_media_finance_and_mobile_student_api(self):
        User = get_user_model()
        student_user = User.objects.create_user("student", "student@example.com", "pass12345")
        participant = Participant.objects.create(
            event=self.event,
            user=student_user,
            full_name="طالب موبايل",
            phone="01088888888",
            email="student-mobile@example.com",
            status=RegistrationStatus.APPROVED,
        )
        MediaItem.objects.create(event=self.event, type=MediaItem.Type.NEWS, title="خبر تجريبي", body="نص الخبر", published=True)
        media_response = self.client.get(reverse("public-media", args=[self.event.slug]))
        self.assertEqual(media_response.status_code, 200)
        self.assertContains(media_response, "خبر تجريبي")

        self.client.login(username="admin", password="pass12345")
        ticket_type_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "ticket_type",
                "ticket_type-event": self.event.id,
                "ticket_type-name": "تذكرة اختبار",
                "ticket_type-price": "0",
                "ticket_type-currency": "EGP",
                "ticket_type-capacity": "20",
                "ticket_type-active": "on",
            },
        )
        self.assertEqual(ticket_type_response.status_code, 302)
        ticket_type = TicketType.objects.get(name="تذكرة اختبار")
        issue_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "issue",
                "issue-event": self.event.id,
                "issue-participant_code": participant.tracking_code,
                "issue-ticket_type": ticket_type.id,
            },
        )
        self.assertEqual(issue_response.status_code, 302)
        self.assertTrue(Ticket.objects.filter(participant=participant, ticket_type=ticket_type).exists())

        paid_participant = Participant.objects.create(event=self.event, full_name="مشارك مدفوع", phone="01018181818", email="paid@example.com", status=RegistrationStatus.APPROVED)
        paid_type_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "ticket_type",
                "ticket_type-event": self.event.id,
                "ticket_type-name": "تذكرة مدفوعة",
                "ticket_type-price": "100",
                "ticket_type-currency": "EGP",
                "ticket_type-capacity": "20",
                "ticket_type-active": "on",
            },
        )
        self.assertEqual(paid_type_response.status_code, 302)
        paid_type = TicketType.objects.get(name="تذكرة مدفوعة")
        coupon_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "coupon",
                "coupon-event": self.event.id,
                "coupon-code": "SAVE50",
                "coupon-discount_type": Coupon.DiscountType.PERCENT,
                "coupon-value": "50",
                "coupon-max_uses": "2",
                "coupon-active": "on",
            },
        )
        self.assertEqual(coupon_response.status_code, 302)
        paid_issue_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "issue",
                "issue-event": self.event.id,
                "issue-participant_code": paid_participant.tracking_code,
                "issue-ticket_type": paid_type.id,
                "issue-coupon_code": "SAVE50",
            },
        )
        self.assertEqual(paid_issue_response.status_code, 302)
        paid_ticket = Ticket.objects.get(participant=paid_participant, ticket_type=paid_type)
        self.assertEqual(str(paid_ticket.amount), "50.00")
        self.assertTrue(paid_ticket.invoice_number)
        self.assertTrue(Invoice.objects.filter(ticket=paid_ticket, total=paid_ticket.amount).exists())
        coupon = Coupon.objects.get(event=self.event, code="SAVE50")
        self.assertEqual(coupon.used_count, 1)

        payment_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "ticket_payment",
                "ticket": paid_ticket.id,
                "payment_status": Ticket.PaymentStatus.PAID,
            },
        )
        self.assertEqual(payment_response.status_code, 302)
        paid_ticket.refresh_from_db()
        self.assertEqual(paid_ticket.payment_status, Ticket.PaymentStatus.PAID)
        self.assertTrue(paid_ticket.receipt_number)

        cancel_response = self.client.post(reverse("admin-finance"), {"form_kind": "ticket_cancel", "ticket": paid_ticket.id})
        self.assertEqual(cancel_response.status_code, 302)
        paid_ticket.refresh_from_db()
        self.assertTrue(paid_ticket.cancelled)

        old_qr_code = paid_ticket.qr_code
        reissue_response = self.client.post(reverse("admin-finance"), {"form_kind": "ticket_reissue", "ticket": paid_ticket.id})
        self.assertEqual(reissue_response.status_code, 302)
        paid_ticket.refresh_from_db()
        self.assertFalse(paid_ticket.cancelled)
        self.assertNotEqual(paid_ticket.qr_code, old_qr_code)

        ticket_api_response = self.client.get(f"/api/tickets/?payment_status={Ticket.PaymentStatus.PAID}&search={paid_ticket.qr_code}")
        self.assertEqual(ticket_api_response.status_code, 200)
        ticket_payload = ticket_api_response.json()
        ticket_items = ticket_payload.get("results", ticket_payload)
        self.assertTrue(any(item["id"] == paid_ticket.id for item in ticket_items))

        refund_response = self.client.post(
            reverse("admin-finance"),
            {
                "form_kind": "refund",
                "refund-event": self.event.id,
                "refund-ticket": paid_ticket.id,
                "refund-participant": paid_participant.id,
                "refund-amount": "50",
                "refund-reason": "طلب استرداد اختبار",
                "refund-status": Refund.Status.PAID,
            },
        )
        self.assertEqual(refund_response.status_code, 302)
        paid_ticket.refresh_from_db()
        self.assertEqual(paid_ticket.payment_status, Ticket.PaymentStatus.REFUNDED)
        self.assertTrue(Refund.objects.filter(ticket=paid_ticket, status=Refund.Status.PAID).exists())

        token_response = self.client.post(reverse("token_obtain_pair"), {"username": "student", "password": "pass12345"})
        access = token_response.json()["access"]
        mobile_response = self.client.get("/api/mobile/student/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(mobile_response.status_code, 200)
        self.assertEqual(mobile_response.json()["participant"]["full_name"], "طالب موبايل")


class PlatformEducationReportTests(EventOSTestCase):
    def test_user_role_and_education_management_pages(self):
        self.client.login(username="admin", password="pass12345")
        create_user_response = self.client.post(
            reverse("admin-users"),
            {
                "form_kind": "create_user",
                "username": "manager",
                "email": "manager@example.com",
                "password": "pass12345",
                "role": Role.EVENT_MANAGER,
                "organization": self.org.id,
                "assigned_events": [self.event.id],
                "is_staff": "on",
                "is_active": "on",
            },
        )
        self.assertEqual(create_user_response.status_code, 302)
        manager = get_user_model().objects.get(username="manager")
        self.assertEqual(manager.profile.role, Role.EVENT_MANAGER)
        self.assertTrue(manager.profile.assigned_events.filter(pk=self.event.pk).exists())

        admin_response = self.client.post(
            reverse("admin-education"),
            {"form_kind": "admin", "admin-organization": self.org.id, "admin-name": "إدارة اختبار", "admin-governorate": "القاهرة"},
        )
        self.assertEqual(admin_response.status_code, 302)
        education_admin = EducationAdministration.objects.get(name="إدارة اختبار")
        school_response = self.client.post(
            reverse("admin-education"),
            {"form_kind": "school", "school-administration": education_admin.id, "school-name": "مدرسة اختبار", "school-city": "القاهرة", "school-is_active": "on"},
        )
        self.assertEqual(school_response.status_code, 302)
        self.assertTrue(School.objects.filter(name="مدرسة اختبار").exists())
        group_response = self.client.post(
            reverse("admin-education"),
            {"form_kind": "group", "group-event": self.event.id, "group-name": "مجموعة اختبار", "group-capacity": "25"},
        )
        self.assertEqual(group_response.status_code, 302)
        self.assertTrue(ParticipantGroup.objects.filter(name="مجموعة اختبار").exists())

    def test_platform_admin_backup_and_final_report(self):
        self.client.login(username="admin", password="pass12345")
        app_response = self.client.post(
            reverse("admin-platform"),
            {
                "form_kind": "app",
                "app-platform": "android",
                "app-version": "2.0.0",
                "app-apk_url": "https://example.com/app.apk",
                "app-update_message": "تحديث اختباري",
                "app-min_supported_version": "1.0.0",
                "app-release_notes": "ملاحظات",
                "app-active": "on",
                "app-released_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(app_response.status_code, 302)
        self.assertTrue(AppVersion.objects.filter(version="2.0.0").exists())

        plan_response = self.client.post(
            reverse("admin-platform"),
            {
                "form_kind": "plan",
                "plan-name": "خطة اختبار",
                "plan-max_events": "5",
                "plan-max_participants": "1000",
                "plan-monthly_price": "100",
                "plan-features": '["reports"]',
                "plan-active": "on",
            },
        )
        self.assertEqual(plan_response.status_code, 302)
        self.assertTrue(SubscriptionPlan.objects.filter(name="خطة اختبار").exists())

        backup_response = self.client.post(reverse("admin-platform"), {"form_kind": "backup", "backup-organization": self.org.id, "backup-job_type": "metadata_snapshot"})
        self.assertEqual(backup_response.status_code, 302)
        self.assertTrue(BackupJob.objects.filter(organization=self.org, status=BackupJob.Status.DONE).exists())

        Participant.objects.create(event=self.event, full_name="مشارك تقرير", phone="01099911111", status=RegistrationStatus.APPROVED)
        report_response = self.client.get(reverse("admin-event-final-report", args=[self.event.id]))
        self.assertEqual(report_response.status_code, 200)
        self.assertTrue(ReportSnapshot.objects.filter(event=self.event, report_type="final").exists())
        pdf_response = self.client.get(reverse("admin-event-final-report", args=[self.event.id]) + "?download=pdf")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")

    def test_report_excel_exports(self):
        participant = Participant.objects.create(event=self.event, full_name="مشارك تصدير", phone="01099922222", email="export@example.com", status=RegistrationStatus.APPROVED)
        services.perform_checkin(self.event, participant.qr_code, actor=self.admin, gate="A", device="unit-test")
        certificate = services.issue_certificate(participant, actor=self.admin)
        violation_type = ViolationType.objects.create(event=self.event, name="مخالفة تصدير", points_penalty=2)
        services.record_violation(participant, violation_type, reported_by=self.admin, notes="اختبار تصدير")
        self.assertTrue(CheckInLog.objects.filter(participant=participant).exists())
        self.assertTrue(Certificate.objects.filter(pk=certificate.pk).exists())

        self.client.login(username="admin", password="pass12345")
        for url_name in [
            "admin-event-participants-export",
            "admin-event-attendance-export",
            "admin-event-certificates-export",
            "admin-event-workshops-export",
            "admin-event-violations-export",
        ]:
            response = self.client.get(reverse(url_name, args=[self.event.id]))
            self.assertEqual(response.status_code, 200)
            self.assertIn("spreadsheetml", response["Content-Type"])
