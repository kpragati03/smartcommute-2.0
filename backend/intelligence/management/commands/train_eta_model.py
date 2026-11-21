"""Train the ML ETA model from simulator history CSV.

Training data is SYNTHETIC demo data (simulator --export-history, seed 42),
not real trips. Metrics are computed on a time-held-out split and reported
honestly for both the 25 km/h baseline and the ML model.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from intelligence import training


class Command(BaseCommand):
    help = "Train ML ETA model from simulator history CSV (synthetic demo data)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(training.DEFAULT_CSV_PATH),
                            help="Path to history CSV (default: intelligence/data/history.csv)")
        parser.add_argument("--model-path", default=str(training.DEFAULT_MODEL_PATH))
        parser.add_argument("--metrics-path", default=str(training.DEFAULT_METRICS_PATH))

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        if not csv_path.exists():
            raise CommandError(
                f"CSV not found: {csv_path}. Generate it with: "
                "python3 simulator/simulator.py --export-history <path> --backfill-days 30 --seed 42")
        metrics = training.train_eta_model(
            csv_path, model_path=options["model_path"], metrics_path=options["metrics_path"])
        b, m = metrics["baseline"], metrics["ml"]
        self.stdout.write(f"Rows: {metrics['n_rows_total']} "
                          f"(train {metrics['n_train']}, held-out test {metrics['n_test']}, "
                          f"dropped-no-distance {metrics['n_dropped_no_distance']})")
        self.stdout.write(f"Baseline (distance/25km/h): MAE={b['mae']} min  RMSE={b['rmse']} min  n={b['n']}")
        self.stdout.write(f"ML (GradientBoosting):      MAE={m['mae']} min  RMSE={m['rmse']} min  n={m['n']}")
        if b["mae"]:
            gain = (b["mae"] - m["mae"]) / b["mae"] * 100
            self.stdout.write(f"ML MAE vs baseline: {gain:+.1f}% (positive = ML better)")
        self.stdout.write(f"Model saved: {options['model_path']}")
        self.stdout.write(f"Metrics saved: {options['metrics_path']}")
        self.stdout.write("NOTE: trained on SYNTHETIC simulator data — not real-world accuracy.")
