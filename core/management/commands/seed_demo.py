from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core import services
from core.models import (
    AppVersion,
    Badge,
    Broadcast,
    CertificateTemplate,
    EducationAdministration,
    Event,
    EventDay,
    Expense,
    Hall,
    IncidentViolation,
    MediaItem,
    Organization,
    Participant,
    ParticipantGroup,
    PointRule,
    RegistrationStatus,
    Role,
    School,
    Session,
    SOSReport,
    Speaker,
    Sponsor,
    SupportTicket,
    Survey,
    SurveyQuestion,
    Ticket,
    TicketType,
    Track,
    UserProfile,
    VIPInvitation,
    ViolationType,
    Volunteer,
    VolunteerShift,
    Workshop,
)


class Command(BaseCommand):
    help = "Seed Event Operating System with practical Arabic demo data."

    def handle(self, *args, **options):
        User = get_user_model()
        admin, _ = User.objects.get_or_create(username="admin", defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True})
        admin.set_password("admin12345")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        org_admin, _ = User.objects.get_or_create(username="orgadmin", defaults={"email": "orgadmin@example.com", "is_staff": True})
        org_admin.set_password("admin12345")
        org_admin.save()

        checkin_user, _ = User.objects.get_or_create(username="checkin", defaults={"email": "checkin@example.com", "is_staff": True})
        checkin_user.set_password("admin12345")
        checkin_user.save()

        org, _ = Organization.objects.get_or_create(
            slug="future-schools",
            defaults={
                "name": "إدارة مدارس المستقبل",
                "contact_email": "events@future-schools.example",
                "contact_phone": "01000000000",
                "address": "القاهرة",
            },
        )
        conf_org, _ = Organization.objects.get_or_create(
            slug="tech-summit-org",
            defaults={
                "name": "مؤسسة قمة التقنية",
                "contact_email": "hello@techsummit.example",
                "contact_phone": "01111111111",
                "address": "مدينة نصر",
                "primary_color": "#1d4ed8",
                "accent_color": "#be123c",
            },
        )

        UserProfile.objects.update_or_create(user=admin, defaults={"role": Role.SUPER_ADMIN})
        UserProfile.objects.update_or_create(user=org_admin, defaults={"role": Role.ORGANIZATION_ADMIN, "organization": org})
        UserProfile.objects.update_or_create(user=checkin_user, defaults={"role": Role.CHECKIN_STAFF, "organization": org})

        now = timezone.now()
        education_event, _ = Event.objects.get_or_create(
            organization=org,
            slug="student-innovation-camp",
            defaults={
                "name": "معسكر الابتكار الطلابي",
                "event_type": Event.EventType.CAMP,
                "short_description": "فعالية تعليمية للطلاب تجمع الورش والمسابقات والتوجيه.",
                "description": "معسكر عملي لإدارة حضور الطلاب والورش والشهادات والدعم داخل تجربة واحدة.",
                "venue_name": "مركز التعليم الإبداعي",
                "venue_address": "القاهرة الجديدة",
                "starts_at": now + timedelta(days=7),
                "ends_at": now + timedelta(days=9),
                "capacity": 250,
                "public_instructions": "يرجى الحضور قبل الموعد بنصف ساعة ومعك التذكرة.",
            },
        )
        conference_event, _ = Event.objects.get_or_create(
            organization=conf_org,
            slug="cairo-tech-conference",
            defaults={
                "name": "مؤتمر القاهرة للتقنية",
                "event_type": Event.EventType.CONFERENCE,
                "short_description": "مؤتمر للشركات والمتحدثين والرعاة حول حلول SaaS والذكاء الاصطناعي.",
                "description": "تجربة مؤتمر كاملة تشمل VIP ومتحدثين ورعاة وجدول وشاشات عرض.",
                "venue_name": "قاعة النيل للمؤتمرات",
                "venue_address": "القاهرة",
                "starts_at": now + timedelta(days=21),
                "ends_at": now + timedelta(days=22),
                "capacity": 600,
                "public_instructions": "الدخول عبر البوابة الرئيسية لحاملي QR.",
            },
        )

        education_event.min_attendance_percent_for_certificate = 50
        education_event.save(update_fields=["min_attendance_percent_for_certificate", "updated_at"])

        for event in [education_event, conference_event]:
            services.ensure_default_modules(event, actor=admin)
            services.ensure_registration_form(event)
            PointRule.objects.get_or_create(event=event, trigger="checkin", defaults={"name": "نقاط الحضور", "value": 10})
            Badge.objects.get_or_create(event=event, name="حاضر ملتزم", defaults={"description": "يمنح لمن يسجل الحضور", "points_required": 10, "auto_award": True})
            CertificateTemplate.objects.get_or_create(event=event, certificate_type="attendance", defaults={"name": "شهادة حضور", "title": "شهادة حضور"})
            AppVersion.objects.get_or_create(platform="android", version="1.0.0", defaults={"apk_url": "https://example.com/app.apk", "update_message": "أحدث إصدار تجريبي متاح", "min_supported_version": "1.0.0"})

        checkin_user.profile.assigned_events.add(education_event)
        org_admin.profile.assigned_events.add(education_event)

        admin_area, _ = EducationAdministration.objects.get_or_create(organization=org, name="إدارة شرق القاهرة", governorate="القاهرة")
        school, _ = School.objects.get_or_create(administration=admin_area, name="مدرسة المستقبل الرسمية", defaults={"city": "القاهرة"})
        group, _ = ParticipantGroup.objects.get_or_create(event=education_event, name="مجموعة أ", defaults={"capacity": 35})

        day1, _ = EventDay.objects.get_or_create(event=education_event, date=(now + timedelta(days=7)).date(), defaults={"name": "اليوم الأول", "order": 1})
        day2, _ = EventDay.objects.get_or_create(event=education_event, date=(now + timedelta(days=8)).date(), defaults={"name": "اليوم الثاني", "order": 2})
        main_hall, _ = Hall.objects.get_or_create(event=education_event, name="القاعة الرئيسية", defaults={"capacity": 180, "equipment": "شاشة، صوت، إنترنت"})
        lab_hall, _ = Hall.objects.get_or_create(event=education_event, name="معمل الابتكار", defaults={"capacity": 35, "equipment": "أجهزة تدريب"})
        track, _ = Track.objects.get_or_create(event=education_event, name="مسار الابتكار", defaults={"description": "ورش وجلسات تطبيقية"})

        trainer, _ = Speaker.objects.get_or_create(event=education_event, name="د. سلمى محمود", defaults={"title": "مدربة ابتكار", "bio": "متخصصة في تصميم تجارب التعلم."})
        speaker, _ = Speaker.objects.get_or_create(event=conference_event, name="م. أحمد فؤاد", defaults={"title": "خبير SaaS", "bio": "يبني منصات تشغيلية قابلة للتوسع."})
        session, _ = Session.objects.get_or_create(
            event=education_event,
            title="افتتاح المعسكر",
            defaults={"day": day1, "track": track, "hall": main_hall, "starts_at": now + timedelta(days=7, hours=1), "ends_at": now + timedelta(days=7, hours=2), "status": Session.Status.NOT_STARTED},
        )
        session.speakers.add(trainer)
        Session.objects.get_or_create(
            event=conference_event,
            title="مستقبل منصات الفعاليات",
            defaults={"hall": Hall.objects.get_or_create(event=conference_event, name="قاعة النيل", defaults={"capacity": 450})[0], "starts_at": now + timedelta(days=21, hours=1), "ends_at": now + timedelta(days=21, hours=2), "status": Session.Status.NOT_STARTED},
        )[0].speakers.add(speaker)

        workshop, _ = Workshop.objects.get_or_create(
            event=education_event,
            title="تصميم مشروع ناشئ",
            defaults={"trainer": trainer, "hall": lab_hall, "starts_at": now + timedelta(days=7, hours=3), "ends_at": now + timedelta(days=7, hours=5), "capacity": 25, "points": 15, "requirements": "إحضار لابتوب إن أمكن"},
        )
        Workshop.objects.get_or_create(
            event=education_event,
            title="عرض الأفكار",
            defaults={"trainer": trainer, "hall": main_hall, "starts_at": now + timedelta(days=8, hours=3), "ends_at": now + timedelta(days=8, hours=4), "capacity": 120, "points": 10},
        )

        participants = []
        for index in range(1, 9):
            participant, _ = Participant.objects.get_or_create(
                event=education_event,
                phone=f"0100000000{index}",
                defaults={
                    "full_name": f"طالب تجريبي {index}",
                    "email": f"student{index}@example.com",
                    "school": school,
                    "education_administration": admin_area,
                    "governorate": "القاهرة",
                    "age": 15 + index % 3,
                    "gender": "ذكر" if index % 2 else "أنثى",
                    "group": group,
                    "status": RegistrationStatus.APPROVED if index < 6 else RegistrationStatus.PENDING_REVIEW,
                },
            )
            participants.append(participant)

        volunteer_participant, _ = Participant.objects.get_or_create(
            event=education_event,
            phone="01099999999",
            defaults={"full_name": "متطوع تجريبي", "email": "volunteer@example.com", "registration_type": Participant.RegistrationType.VOLUNTEER, "status": RegistrationStatus.APPROVED},
        )
        volunteer, _ = Volunteer.objects.get_or_create(participant=volunteer_participant, defaults={"role": Volunteer.RoleChoice.CHECKIN, "area": "البوابة الرئيسية", "accepted": True})
        VolunteerShift.objects.get_or_create(volunteer=volunteer, starts_at=now + timedelta(days=7), ends_at=now + timedelta(days=7, hours=8), defaults={"shift_type": VolunteerShift.ShiftType.FULL_DAY, "location": "البوابة"})

        services.enroll_workshop(workshop, participants[0], actor=admin)
        if not participants[0].checked_in_at:
            services.perform_checkin(education_event, participants[0].qr_code, actor=checkin_user, gate="البوابة الرئيسية", device="demo-scanner")
        services.perform_checkin(education_event, participants[0].qr_code, action="workshop", actor=checkin_user, workshop=workshop, gate="معمل الابتكار", device="demo-scanner")
        services.award_points(participants[1], 20, "منح يدوي للتميز", actor=admin)

        violation_type, _ = ViolationType.objects.get_or_create(event=education_event, name="مخالفة تنظيمية", defaults={"default_action": "إنذار ومنع شهادة مؤقت", "blocks_certificate": True, "points_penalty": 5})
        if not IncidentViolation.objects.filter(participant=participants[2], violation_type=violation_type).exists():
            services.record_violation(participants[2], violation_type, reported_by=admin, notes="تجربة منع شهادة بسبب مخالفة", location="القاعة الرئيسية")

        certificate = services.issue_certificate(participants[0], actor=admin)
        services.send_event_email(education_event, participants[0].email, "شهادة الحضور", f"تم إصدار شهادتك: {certificate.serial_number}", participant=participants[0])

        SupportTicket.objects.get_or_create(event=education_event, tracking_code="SUP-DEMO-001", defaults={"participant": participants[3], "category": "مشكلة في التسجيل", "subject": "تعديل بيانات", "message": "أرغب في تعديل اسم المدرسة."})
        SOSReport.objects.get_or_create(event=education_event, description="ازدحام عند البوابة", defaults={"reporter": checkin_user, "category": SOSReport.Category.CROWD, "priority": 2, "location": "البوابة الرئيسية"})
        VIPInvitation.objects.get_or_create(event=conference_event, name="أ. ليلى منصور", defaults={"title": "ضيف شرف", "email": "vip@example.com", "reserved_seat": "A1", "special_entrance": "مدخل VIP", "status": VIPInvitation.Status.CONFIRMED})
        Sponsor.objects.get_or_create(event=conference_event, name="شركة النيل الرقمية", defaults={"level": Sponsor.Level.GOLD, "sponsorship_value": 50000, "benefits": "ظهور في الموقع والشاشة والشهادة", "show_on_site": True})
        MediaItem.objects.get_or_create(event=education_event, title="إطلاق معسكر الابتكار الطلابي", defaults={"type": MediaItem.Type.NEWS, "body": "خبر تجريبي عن انطلاق الفعالية واستقبال الطلاب.", "published": True})
        Expense.objects.get_or_create(event=education_event, category="تشغيل", description="مواد تدريبية", defaults={"amount": 3500})
        Broadcast.objects.get_or_create(event=education_event, title="تذكير بالحضور", defaults={"audience": "المقبولون", "channel": Broadcast.Channel.EMAIL, "message": "نذكركم بموعد المعسكر وتعليمات الحضور.", "created_by": admin, "status": "draft"})
        survey, _ = Survey.objects.get_or_create(event=education_event, title="تقييم المعسكر", defaults={"active": True, "certificate_required": False})
        SurveyQuestion.objects.get_or_create(survey=survey, text="ما تقييمك للتنظيم؟", defaults={"question_type": SurveyQuestion.QuestionType.STARS, "order": 1})
        ticket_type, _ = TicketType.objects.get_or_create(event=conference_event, name="تذكرة مجانية", defaults={"price": 0, "capacity": 300})
        Ticket.objects.get_or_create(event=conference_event, participant=Participant.objects.get_or_create(event=conference_event, phone="01122222222", defaults={"full_name": "حاضر مؤتمر تجريبي", "email": "attendee@example.com", "status": RegistrationStatus.APPROVED})[0], defaults={"ticket_type": ticket_type})

        self.stdout.write(self.style.SUCCESS("Demo data created. Login: admin / admin12345, orgadmin / admin12345, checkin / admin12345"))
