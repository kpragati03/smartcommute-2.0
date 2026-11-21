"""Fill actual_eta_minutes on pending ETAPrediction rows.

For each prediction without an actual, find the first LocationHistory row
for that vehicle recorded at/after the prediction where distance_covered_km
reaches the stop's distance_from_start_km. Actual = elapsed minutes between
prediction creation and that row (telemetry-granularity approximation).

Limitation: assumes forward travel (distance increasing toward the stop).
Reverse-direction arrivals (distance decreasing through the stop) are not
detected and stay pending.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from tracking.models import ETAPrediction, LocationHistory


class Command(BaseCommand):
    help = "Evaluate pending ETA predictions against LocationHistory arrivals."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1000,
                            help="Max pending predictions to process per run")

    def handle(self, *args, **options):
        pending = (ETAPrediction.objects.filter(actual_eta_minutes__isnull=True)
                   .select_related("vehicle", "stop").order_by("created_at")[:options["limit"]])
        evaluated = still_pending = 0
        now = timezone.now()
        for pred in pending:
            arrival = (LocationHistory.objects
                       .filter(vehicle=pred.vehicle,
                               recorded_at__gte=pred.created_at,
                               distance_covered_km__gte=pred.stop.distance_from_start_km)
                       .order_by("recorded_at").first())
            if arrival is None:
                still_pending += 1
                continue
            actual = (arrival.recorded_at - pred.created_at).total_seconds() / 60.0
            pred.actual_eta_minutes = round(actual, 2)
            pred.evaluated_at = now
            pred.save(update_fields=["actual_eta_minutes", "evaluated_at"])
            evaluated += 1
        self.stdout.write(f"Evaluated: {evaluated}, still pending (no arrival yet): {still_pending}")
