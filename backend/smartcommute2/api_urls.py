from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (RegisterView, LoginView, RefreshView, MeView, OrganisationRegisterView,
                        OrganisationListView, PasswordResetView, PasswordResetConfirmView)
from fleet.views import (RouteViewSet, StopViewSet, VehicleViewSet, DriverViewSet,
                         ScheduleViewSet, TripViewSet, DeviceViewSet, TelemetryView,
                         DriverMyTripView, DriverTripActionView, DriverHistoryView)
from tracking.views import LiveVehiclesView, LiveETAView
from commuter.views import (FavouriteRouteView, FavouriteStopView, SavedJourneyView,
                            PassApplyView, PassMineView, PassApplicationListView,
                            PassApproveView, PassRejectView, PassVerifyView, PassQRView,
                            ComplaintView, ComplaintDetailView, FeedbackView, IncidentView,
                            JourneyPlanView)
from notifications.views import NotificationListView, NotificationReadView, NotificationReadAllView
from saas.views import PlanListView, SubscriptionView, SubscriptionUpgradeView

router = DefaultRouter()
router.register("routes", RouteViewSet, basename="route")
router.register("stops", StopViewSet, basename="stop")
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("drivers", DriverViewSet, basename="driver")
router.register("schedules", ScheduleViewSet, basename="schedule")
router.register("trips", TripViewSet, basename="trip")
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("devices/telemetry/", TelemetryView.as_view()),
    path("", include(router.urls)),
    path("auth/register/", RegisterView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("auth/refresh/", RefreshView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("auth/password-reset/", PasswordResetView.as_view()),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view()),
    path("organisations/register/", OrganisationRegisterView.as_view()),
    path("organisations/", OrganisationListView.as_view()),
    path("live/vehicles/", LiveVehiclesView.as_view()),
    path("live/eta/", LiveETAView.as_view()),
    # Wave 2: bidirectional planner lives in commuter (tracking planner is forward-only).
    path("journey/plan/", JourneyPlanView.as_view()),
    path("favourites/routes/", FavouriteRouteView.as_view()),
    path("favourites/stops/", FavouriteStopView.as_view()),
    path("journeys/saved/", SavedJourneyView.as_view()),
    path("passes/apply/", PassApplyView.as_view()),
    path("passes/mine/", PassMineView.as_view()),
    path("passes/applications/", PassApplicationListView.as_view()),
    path("passes/applications/<int:pk>/approve/", PassApproveView.as_view()),
    path("passes/applications/<int:pk>/reject/", PassRejectView.as_view()),
    path("passes/verify/", PassVerifyView.as_view()),
    path("passes/<int:pk>/qr/", PassQRView.as_view()),
    path("complaints/", ComplaintView.as_view()),
    path("complaints/<int:pk>/", ComplaintDetailView.as_view()),
    path("feedback/", FeedbackView.as_view()),
    path("incidents/", IncidentView.as_view()),
    path("notifications/", NotificationListView.as_view()),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view()),
    path("notifications/read-all/", NotificationReadAllView.as_view()),
    path("driver/my-trip/", DriverMyTripView.as_view()),
    path("driver/trips/<int:pk>/<str:action>/", DriverTripActionView.as_view()),
    path("driver/history/", DriverHistoryView.as_view()),
    path("plans/", PlanListView.as_view()),
    path("subscription/", SubscriptionView.as_view()),
    path("subscription/upgrade/", SubscriptionUpgradeView.as_view()),
]

from intelligence.views import (AnalyticsOverviewView, AnalyticsRoutesView,
                                AnalyticsCrowdView, AnalyticsETAAccuracyView)
urlpatterns += [
    path("analytics/overview/", AnalyticsOverviewView.as_view()),
    path("analytics/routes/", AnalyticsRoutesView.as_view()),
    path("analytics/crowd/", AnalyticsCrowdView.as_view()),
    path("analytics/eta-accuracy/", AnalyticsETAAccuracyView.as_view()),
    # Phase 10 (ML intelligence): crowd prediction, eta-accuracy alias, model metrics.
    path("intelligence/", include("intelligence.urls")),
]
