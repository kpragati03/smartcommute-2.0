"""ETA model training pipeline (Phase 10 — ML intelligence).

Trains a per-segment travel-time regressor on stop-to-stop trip history.

DATA HONESTY: the training CSV is SYNTHETIC demo data produced by the
simulator's `--export-history` mode (deterministic, seed 42). It is NOT
real trip data. Metrics reported here measure how well the model fits that
synthetic generator's patterns (peak-hour slowdowns etc.), not real-world
accuracy. Retrain on real LocationHistory-derived segments before any
production claim.

Model choice: GradientBoostingRegressor — handles the nonlinear
hour/passenger effects in segment durations, works well on a few thousand
rows without feature scaling, and is deterministic with a fixed seed.
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASELINE_SPEED_KMPH = 25.0  # contract fallback speed, used for baseline metrics
PEAK_HOURS = {8, 9, 17, 18, 19}  # matches simulator's slow peak windows
TEST_FRACTION = 0.2  # last 20% chronologically = held-out test set
RANDOM_STATE = 42

APP_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = APP_DIR / "models" / "eta_model.joblib"
DEFAULT_METRICS_PATH = APP_DIR / "models" / "eta_metrics.json"
DEFAULT_CSV_PATH = APP_DIR / "data" / "history.csv"


def segment_distance_map_from_db():
    """{(route_name, stop_name): distance_from_start_km} from fleet.Stop rows."""
    from fleet.models import Stop

    out = {}
    for s in Stop.objects.select_related("route").all():
        out[(s.route.name, s.name)] = float(s.distance_from_start_km)
    return out


def _feature_row(distance_km, hour, day_of_week, passengers, route_name, route_categories):
    row = [
        float(distance_km),
        int(hour),
        int(day_of_week),
        int(passengers),
        1 if int(hour) in PEAK_HOURS else 0,
    ]
    row += [1 if route_name == c else 0 for c in route_categories]
    return row


def feature_names(route_categories):
    return (["distance_km", "hour", "day_of_week", "passengers", "is_peak"]
            + [f"route__{c}" for c in route_categories])


def load_training_frame(csv_path, distance_map):
    """Read simulator history CSV, attach segment distances, drop unusable rows.

    Returns (df, n_dropped). df columns include distance_km + duration_minutes.
    """
    df = pd.read_csv(csv_path)
    required = {"timestamp", "route", "stop_from", "stop_to",
                "duration_minutes", "passengers", "day_of_week", "hour"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")

    def seg_km(row):
        a = distance_map.get((row["route"], row["stop_from"]))
        b = distance_map.get((row["route"], row["stop_to"]))
        if a is None or b is None:
            return np.nan
        return abs(b - a)

    df["distance_km"] = df.apply(seg_km, axis=1)
    before = len(df)
    df = df.dropna(subset=["distance_km"])
    df = df[(df["distance_km"] > 0) & (df["duration_minutes"] > 0)]
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df, before - len(df)


def _metrics(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    return {"mae": round(mae, 3), "rmse": round(rmse, 3), "n": int(len(y_true))}


def train_eta_model(csv_path, model_path=None, metrics_path=None, distance_map=None):
    """Train, evaluate on time-held-out split, persist model + metrics.

    Returns the metrics dict (also written to metrics_path as JSON).
    """
    model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
    metrics_path = Path(metrics_path) if metrics_path else DEFAULT_METRICS_PATH
    if distance_map is None:
        distance_map = segment_distance_map_from_db()

    df, n_dropped = load_training_frame(csv_path, distance_map)
    if len(df) < 50:
        raise ValueError(f"Only {len(df)} usable training rows — need at least 50")

    route_categories = sorted(df["route"].unique().tolist())
    X = np.array([
        _feature_row(r.distance_km, r.hour, r.day_of_week, r.passengers, r.route, route_categories)
        for r in df.itertuples()
    ], dtype=float)
    y = df["duration_minutes"].to_numpy(dtype=float)

    split = int(len(df) * (1 - TEST_FRACTION))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    test_distances = df["distance_km"].to_numpy(dtype=float)[split:]

    model = GradientBoostingRegressor(
        n_estimators=250, max_depth=3, learning_rate=0.08,
        subsample=0.9, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)

    ml_pred = np.maximum(model.predict(X_test), 0.1)
    baseline_pred = test_distances / BASELINE_SPEED_KMPH * 60.0

    trained_at = datetime.now(timezone.utc).isoformat()
    metrics = {
        "baseline": _metrics(y_test, baseline_pred),
        "ml": _metrics(y_test, ml_pred),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "n_rows_total": int(len(df)),
        "n_dropped_no_distance": int(n_dropped),
        "split": "time-ordered: last 20% chronologically held out",
        "model": "GradientBoostingRegressor(n_estimators=250, max_depth=3, learning_rate=0.08)",
        "features": feature_names(route_categories),
        "trained_at": trained_at,
        "data_source": (f"synthetic simulator history CSV: {csv_path} "
                        "(--export-history, seed 42) — SYNTHETIC DEMO DATA, not real trips"),
    }

    bundle = {
        "model": model,
        "route_categories": route_categories,
        "feature_names": feature_names(route_categories),
        "trained_at": trained_at,
        "metrics": metrics,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def predict_segment_minutes(bundle, distance_km, hour, day_of_week, passengers, route_name):
    """Predict one segment's travel time (minutes) from a loaded bundle."""
    row = np.array([_feature_row(distance_km, hour, day_of_week, passengers,
                                  route_name, bundle["route_categories"])], dtype=float)
    return float(max(bundle["model"].predict(row)[0], 0.1))
