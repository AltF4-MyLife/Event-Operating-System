from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api

router = DefaultRouter()
router.register("organizations", api.OrganizationViewSet)
router.register("events", api.EventViewSet)
router.register("profiles", api.UserProfileViewSet)
router.register("participants", api.ParticipantViewSet)
router.register("workshops", api.WorkshopViewSet)
router.register("certificates", api.CertificateViewSet)
router.register("broadcasts", api.BroadcastViewSet)
router.register("sos", api.SOSReportViewSet)
router.register("support-tickets", api.SupportTicketViewSet)

for prefix, viewset in api.GENERATED_VIEWSETS.items():
    router.register(prefix, viewset, basename=prefix)

urlpatterns = [
    path("public/events/<slug:event_slug>/register/", api.PublicRegistrationAPIView.as_view(), name="api-public-register"),
    path("mobile/me/", api.MobileMeAPIView.as_view(), name="api-mobile-me"),
    path("mobile/student/", api.MobileStudentDashboardAPIView.as_view(), name="api-mobile-student"),
    path("mobile/supervisor/", api.MobileSupervisorDashboardAPIView.as_view(), name="api-mobile-supervisor"),
    path("mobile/volunteer/", api.MobileVolunteerDashboardAPIView.as_view(), name="api-mobile-volunteer"),
    path("mobile/app-version/", api.MobileAppVersionAPIView.as_view(), name="api-mobile-app-version"),
    path("mobile/checkin/", api.MobileCheckInAPIView.as_view(), name="api-mobile-checkin"),
] + router.urls
