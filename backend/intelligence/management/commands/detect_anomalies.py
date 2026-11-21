"""Rule-based anomaly detection over recent LocationHistory.

Rules: stale GPS (>120s, active vehicle), route deviation (>300m from
polyline), speed jump (|Δspeed| >60 km/h), impossible jump (>2km in <10s).
Creates deduped Incident rows (same vehicle+type suppressed for 30 min).
"""
from django.core.management.base import BaseCommand

from intelligence.services import detect_anomalies


class Command(BaseCommand):
    help = "Detect telemetry anomalies and create deduped Incident rows."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=float, default=2.0,
                            help="Look-back window in hours (default 2)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report counts without creating incidents")

    def handle(self, *args, **options):
        s = detect_anomalies(hours=options["hours"], create=not options["dry_run"])
        self.stdout.write(f"Checked active vehicles: {s['checked_vehicles']}")
        self.stdout.write(f"Stale GPS flagged:       {s['stale_gps']}")
        self.stdout.write(f"Route deviation flagged: {s['route_deviation']}")
        self.stdout.write(f"Speed jump flagged:      {s['speed_jump']}")
        self.stdout.write(f"Impossible jump flagged: {s['impossible_jump']}")
        self.stdout.write(f"Incidents created: {s['incidents_created']}, "
                          f"deduped: {s['deduped']}, "
                          f"skipped (no reporter user): {s['skipped_no_reporter']}")
        if options["dry_run"]:
            self.stdout.write("(dry-run: no incidents written)")
