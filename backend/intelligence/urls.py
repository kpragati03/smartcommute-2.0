from django.urls import path

from .views import AnalyticsETAAccuracyView, CrowdPredictionView, ETAModelMetricsView

urlpatterns = [
    path("crowd-prediction/", CrowdPredictionView.as_view()),
    # Alias of /analytics/eta-accuracy/ (same view, same {baseline, ml} shape).
    path("eta-accuracy/", AnalyticsETAAccuracyView.as_view()),
    path("eta-metrics/", ETAModelMetricsView.as_view()),
]
